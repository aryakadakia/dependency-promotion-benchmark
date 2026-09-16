#!/usr/bin/env python3
"""
Every figure the manuscript reports, computed in one place, emitted as JSON.

This exists because the previous draft's numbers were computed inline, printed
once and transcribed. Nothing connected them to the data, so when the frame was
extended and the rubric revised, the prose silently went stale. A figure that
cannot be recomputed cannot be checked.

    python figures.py                 # JSON to stdout
    python figures.py --save          # write ../paper/figures.json
"""
import argparse, json, pathlib, collections, statistics, re, sys
import rubric_v07 as R
from reliability import gwet_ac1, raw_agreement, krippendorff_nominal, prevalence

ROOT = pathlib.Path(__file__).parent.parent
JUDGED = ["judged_v06_local.json", "judged_v06_commercial.json", "judged_v07_sonnet.json"]


def load():
    fr = json.loads((ROOT / "runs" / "frame.json").read_text())
    meta = {(t["scenario"], t["model"], t["condition"], t["sample"], t["turn"]): t
            for t in fr["turns"]}
    rows = [r for f in JUDGED for r in json.loads((ROOT / "runs" / f).read_text())]
    hum = json.loads((ROOT / "runs" / "handcoded.json").read_text())["scores"]
    return fr, meta, rows, hum


def panel(rows):
    out = collections.defaultdict(dict)
    for r in rows:
        k = (r["scenario"], r["model"], r["condition"], r["sample"], r["turn"])
        for j, sc in r["judges"].items():
            out[k].setdefault(j, {}).update(
                {d: v for d, v in sc.items() if not d.endswith("_init")})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--save", action="store_true")
    a = ap.parse_args()
    fr, meta, rows, hum = load()
    units = panel(rows)
    F = {}

    # --- corpus and frame descriptives -----------------------------------
    valid = [t for t in fr["turns"] if not t.get("invalid_reason")]
    F["frame_turns"] = fr["n"]
    F["frame_flagged"] = len(fr["turns"]) - len(valid)
    F["frame_analysed"] = len(valid)
    F["frame_live_stratum"] = sum(1 for t in fr["turns"] if t.get("stratum") == "live")
    F["frame_background_stratum"] = sum(1 for t in fr["turns"]
                                        if t.get("stratum") == "background")
    lvl = collections.Counter(
        (re.search(r"sp-(neutral|warm|retention)", t.get("source_file") or "")
         or [None, "unknown"])[1] for t in valid)
    F["frame_analysed_by_prompt"] = dict(lvl)
    F["judges"] = len({j for u in units.values() for j in u})
    F["dimension_scores"] = sum(len(s) for k, u in units.items()
                                if k in meta and not meta[k].get("invalid_reason")
                                for s in u.values())
    F["judge_failures"] = sum(len(r.get("failures") or []) for r in rows)
    cl = collections.Counter((t["scenario"], t["turn"]) for t in fr["turns"])
    F["authored_turns_in_frame"] = len(cl)
    F["generations_per_authored_turn_max"] = max(cl.values())
    F["generations_per_authored_turn_median"] = statistics.median(cl.values())

    stim = collections.defaultdict(set)
    for t in valid:
        for d in t.get("live_dims", []):
            stim[d].add((t["scenario"], t["turn"]))
    F["stimuli_per_dimension"] = {d: len(stim[d]) for d in R.DIMENSIONS}

    # --- human coding ----------------------------------------------------
    def key(uid):
        p = uid.replace("#recode", "").split("|")
        return (p[0], p[1], p[2], int(p[3]), int(p[4]))
    ok = lambda u: (meta.get(key(u)) and not meta[key(u)].get("invalid_reason"))
    first = {u: v for u, v in hum.items() if not u.endswith("#recode") and ok(u)}
    F["coded_turns"] = len(first)
    F["coded_judgements"] = sum(len([d for d in v if not d.endswith("_init")])
                                for v in first.values())
    F["blind_repeats"] = sum(1 for u in hum if u.endswith("#recode") and ok(u))
    F["coded_turns_with_hidden_context"] = sum(
        1 for u in first if meta[key(u)]["turn"] > 3)
    F["coded_turn_position_median"] = statistics.median(
        meta[key(u)]["turn"] for u in first)

    # --- judge vs human, per dimension ------------------------------------
    jh, pts = {}, []
    for d in R.DIMENSIONS:
        u = []
        for uid, hs in first.items():
            if d not in hs:
                continue
            k = key(uid)
            jv = [s[d] for s in units.get(k, {}).values() if d in s]
            if not jv or d not in meta[k].get("live_dims", []):
                continue
            u.append([hs[d], 1 if sum(jv) * 2 > len(jv) else 0])
        if len(u) < 2:
            continue
        jh[d] = {"n": len(u), "prevalence": round(prevalence(u), 4),
                 "agreement": round(raw_agreement(u), 4),
                 "ac1": round(gwet_ac1(u), 4)}
        pts.append((d, prevalence(u), gwet_ac1(u)))
    F["judge_vs_human"] = jh
    xs = [abs(p[1] - 0.5) for p in pts]
    ys = [p[2] for p in pts]
    mx, my = statistics.mean(xs), statistics.mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = (sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys)) ** 0.5
    F["r_prevalence_ac1"] = round(num / den, 3)
    ext = [p for p in pts if p[1] < 0.15 or p[1] > 0.85]
    mid = [p for p in pts if 0.35 <= p[1] <= 0.65]
    F["mean_ac1_extreme_prevalence"] = round(statistics.mean(p[2] for p in ext), 3)
    F["mean_ac1_mid_prevalence"] = round(statistics.mean(p[2] for p in mid), 3)
    F["n_dimensions_extreme"] = len(ext)
    F["n_dimensions_mid"] = len(mid)

    # --- per judge, and pairwise ------------------------------------------
    js = sorted({j for u in units.values() for j in u})
    per = {}
    for j in js:
        u = []
        for uid, hs in first.items():
            k = key(uid)
            sc = units.get(k, {}).get(j)
            if not sc:
                continue
            for d, hv in hs.items():
                if d in sc and d in meta[k].get("live_dims", []):
                    u.append([hv, sc[d]])
        if len(u) >= 2:
            per[j] = {"n": len(u), "agreement": round(raw_agreement(u), 4),
                      "ac1": round(gwet_ac1(u), 4)}
    F["per_judge_vs_human"] = per
    F["mean_judge_human_ac1"] = round(
        statistics.mean(v["ac1"] for v in per.values()), 3)

    pair = {}
    for i, x in enumerate(js):
        for y in js[i + 1:]:
            u = []
            for k, sc in units.items():
                m = meta.get(k)
                if not m or m.get("invalid_reason"):
                    continue
                if x in sc and y in sc:
                    for d in set(sc[x]) & set(sc[y]):
                        if d in m.get("live_dims", []):
                            u.append([sc[x][d], sc[y][d]])
            if len(u) >= 2:
                pair[f"{x} | {y}"] = round(gwet_ac1(u), 4)
    F["pairwise_judge_ac1"] = pair
    F["mean_judge_judge_ac1"] = round(statistics.mean(pair.values()), 3)
    tier = lambda j: "open" if j.startswith("ollama") else "commercial"
    cc = [v for k, v in pair.items() if all(tier(p.strip()) == "commercial"
                                            for p in k.split("|"))]
    oo = [v for k, v in pair.items() if all(tier(p.strip()) == "open"
                                            for p in k.split("|"))]
    F["mean_commercial_pair_ac1"] = round(statistics.mean(cc), 3)
    F["mean_open_pair_ac1"] = round(statistics.mean(oo), 3)
    VENDOR = {"anthropic:claude-sonnet-5": "anthropic",
              "anthropic:claude-haiku-4-5": "anthropic",
              "google:gemini-3.7-flash": "google", "ollama:gemma3:12b": "google",
              "ollama:qwen3:14b": "alibaba", "ollama:llama3.1:8b": "meta"}
    same = [v for k, v in pair.items()
            if len({VENDOR.get(p.strip()) for p in k.split("|")}) == 1]
    cross = [v for k, v in pair.items()
             if len({VENDOR.get(p.strip()) for p in k.split("|")}) == 2]
    F["mean_same_vendor_pair_ac1"] = round(statistics.mean(same), 3)
    F["mean_cross_vendor_pair_ac1"] = round(statistics.mean(cross), 3)
    F["n_same_vendor_pairs"] = len(same)
    F["n_cross_vendor_pairs"] = len(cross)
    top = sorted(pair.items(), key=lambda x: -x[1])[:2]
    F["highest_agreeing_pairs"] = {k: v for k, v in top}
    lla = [v for k, v in pair.items() if "llama3.1:8b" in k]
    F["llama_pair_ac1_min"] = round(min(lla), 3)
    F["llama_pair_ac1_max"] = round(max(lla), 3)

    # --- direction of disagreement ----------------------------------------
    contested = [d for d, v in jh.items() if v["ac1"] < 0.667]
    hi = lo = thi = tlo = 0
    dirn = {}
    for d in R.DIMENSIONS:
        a = b = 0
        for uid, hs in first.items():
            if d not in hs:
                continue
            k = key(uid)
            jv = [s[d] for s in units.get(k, {}).values() if d in s]
            if not jv or d not in meta[k].get("live_dims", []):
                continue
            cons = 1 if sum(jv) * 2 > len(jv) else 0
            a += (hs[d] == 1 and cons == 0)
            b += (hs[d] == 0 and cons == 1)
        if a or b:
            dirn[d] = [a, b]
        thi, tlo = thi + a, tlo + b
        if d in contested:
            hi, lo = hi + a, lo + b
    F["contested_dimensions"] = sorted(contested)
    F["disagreement_direction"] = dirn
    F["contested_disagreements_human_present"] = hi
    F["contested_disagreements_total"] = hi + lo
    F["all_disagreements_human_present"] = thi
    F["all_disagreements_total"] = thi + tlo

    # --- panel reliability table (Table 6) --------------------------------
    from reliability import collect, boot_ci
    data = collect(rows, meta)
    tbl = {}
    for d in R.DIMENSIONS:
        for pop in ("LIVE", "BACKGROUND", "POOLED"):
            c = data.get((d, pop))
            if not c:
                continue
            u = [x for g in c.values() for x in g]
            if len(u) < 2:
                continue
            e = {"units": len(u), "stimuli": len(c),
                 "prevalence": round(prevalence(u), 4),
                 "agreement": round(raw_agreement(u), 4),
                 "alpha": round(krippendorff_nominal(u), 4),
                 "ac1": round(gwet_ac1(u), 4)}
            if pop == "LIVE":
                lo, hi = boot_ci(c, gwet_ac1)
                if lo is not None:
                    e["ci"] = [round(lo, 4), round(hi, 4)]
            tbl.setdefault(d, {})[pop] = e
    F["panel_reliability"] = tbl

    # --- prevalence by dimension and by model (Tables 10, 11) --------------
    EXCL = {"ollama:mistral:7b", "google:gemini-3.1-pro-preview"}
    cons, permodel = {}, collections.defaultdict(lambda: collections.Counter())
    for d in R.DIMENSIONS:
        hits = n = 0
        for k, u in units.items():
            m = meta.get(k)
            if not m or m.get("invalid_reason") or d not in m.get("live_dims", []):
                continue
            if k[1] in EXCL:        # same exclusion as the model-level table
                continue
            jv = [s[d] for s in u.values() if d in s]
            if not jv:
                continue
            c = 1 if sum(jv) * 2 > len(jv) else 0
            n += 1
            hits += c
            if k[1] not in EXCL:
                # Valence grouping, as prevalence.py defines it: PER1 and PER3
                # are harm dimensions and belong in DEP, not in a family of
                # their own.
                fam = {R.HARM: "DEP", R.PROTECTIVE: "PRO",
                       R.OVERCORRECTION: "OVR"}[R.DIMENSIONS[d]["valence"]]
                permodel[k[1]][fam + "_n"] += 1
                permodel[k[1]][fam] += c
                if d == "DEP5":
                    permodel[k[1]]["FMR_n"] += 1
                    permodel[k[1]]["FMR"] += c
        if n:
            cons[d] = {"live_turns": n, "prevalence": round(hits / n, 4)}
    F["prevalence_by_dimension"] = cons
    F["prevalence_by_model"] = {
        m: {f: round(c[f] / c[f + "_n"], 4) for f in ("DEP", "PRO", "OVR", "FMR")
            if c.get(f + "_n")} for m, c in permodel.items()}

    # --- calibration (Table 12) -------------------------------------------
    cal = json.loads((ROOT / "runs" / "calibration.json").read_text())
    b = collections.defaultdict(list); c_ = collections.defaultdict(list)
    for rec in cal:
        for d in rec["dims"]:
            h = rec["human"].get(d)
            if h is None:
                continue
            if rec["baseline"].get(d) is not None:
                b[d].append([h, rec["baseline"][d]])
            if rec["calibrated"].get(d) is not None:
                c_[d].append([h, rec["calibrated"][d]])
    out = {}
    for d in sorted(set(b) | set(c_)):
        e = {"baseline_n": len(b[d]), "calibrated_n": len(c_[d])}
        if len(b[d]) >= 2:
            e["baseline_ac1"] = round(gwet_ac1(b[d]), 4)
        if len(c_[d]) >= 2:
            e["calibrated_ac1"] = round(gwet_ac1(c_[d]), 4)
        out[d] = e
    ab = [x for v in b.values() for x in v]; ac = [x for v in c_.values() for x in v]
    # Bootstrap the difference over scenarios, the unit the split was made on.
    import random
    by_scen_b, by_scen_c = collections.defaultdict(list), collections.defaultdict(list)
    for rec in cal:
        s = rec["key"][0]
        for d in rec["dims"]:
            h = rec["human"].get(d)
            if h is None:
                continue
            if rec["baseline"].get(d) is not None:
                by_scen_b[s].append([h, rec["baseline"][d]])
            if rec["calibrated"].get(d) is not None:
                by_scen_c[s].append([h, rec["calibrated"][d]])
    keys = sorted(set(by_scen_b) | set(by_scen_c))
    rng, diffs = random.Random(7), []
    for _ in range(2000):
        pick = [keys[rng.randrange(len(keys))] for _ in keys]
        ub = [u for s in pick for u in by_scen_b.get(s, [])]
        uc = [u for s in pick for u in by_scen_c.get(s, [])]
        gb, gc = gwet_ac1(ub), gwet_ac1(uc)
        if gb is not None and gc is not None:
            diffs.append(gc - gb)
    diffs.sort()
    lo = diffs[int(0.025 * len(diffs))] if diffs else None
    hi = diffs[int(0.975 * len(diffs))] if diffs else None
    out["ALL"] = {"baseline_n": len(ab), "calibrated_n": len(ac),
                  "baseline_ac1": round(gwet_ac1(ab), 4),
                  "calibrated_ac1": round(gwet_ac1(ac), 4),
                  "change": round(gwet_ac1(ac) - gwet_ac1(ab), 4),
                  "change_ci": [round(lo, 3), round(hi, 3)] if diffs else None}
    F["calibration"] = out

    # --- per-judge, per-dimension, for the claims 4.4 and 5.3 make ---------
    pjd = {}
    for d in ("DEP1", "DEP6"):
        row = {}
        for j in js:
            u = []
            for uid, hs in first.items():
                if d not in hs:
                    continue
                k = key(uid)
                sc = units.get(k, {}).get(j)
                if not sc or d not in sc or d not in meta[k].get("live_dims", []):
                    continue
                u.append([hs[d], sc[d]])
            if len(u) >= 2:
                row[j] = {"n": len(u), "ac1": round(gwet_ac1(u), 4)}
        pjd[d] = row
    F["per_judge_by_dimension"] = pjd

    # --- pre-registered analyses (analysis-plan-v1 sections 2.4, 3, 6) -----
    prov = collections.defaultdict(collections.Counter)
    for r in rows:
        k = (r["scenario"], r["model"], r["condition"], r["sample"], r["turn"])
        m = meta.get(k)
        if not m or m.get("invalid_reason"):
            continue
        for sc in r["judges"].values():
            for d in ("DEP1", "DEP2", "DEP3", "DEP6"):
                if sc.get(d) == 1 and d in m.get("live_dims", []):
                    prov[d][sc.get(d + "_init") or "unrecorded"] += 1
    F["provenance"] = {d: {"n": sum(c.values()),
                           "assistant": round(c["assistant"] / sum(c.values()), 4)}
                       for d, c in prov.items() if sum(c.values())}

    ug = json.loads((ROOT / "runs" / "judged_ungated.json").read_text())
    fu = json.loads((ROOT / "runs" / "frame_ungated.json").read_text())
    um = {(t["scenario"], t["model"], t["condition"], t["sample"], t["turn"]): t
          for t in fu["turns"]}
    hit, tt, seen = collections.Counter(), collections.Counter(), set()
    for r in ug:
        k = (r["scenario"], r["model"], r["condition"], r["sample"], r["turn"])
        m = um.get(k)
        if not m or m.get("all_probes"):
            continue
        seen.add(k)
        for sc in r["judges"].values():
            for d, v in sc.items():
                if d.endswith("_init") or d in R.ALWAYS_LIVE:
                    continue
                tt[d] += 1
                hit[d] += v
    F["off_probe"] = {"turns": len(seen),
                      "by_dimension": {d: round(hit[d] / tt[d], 4) for d in tt},
                      "overall": round(sum(hit.values()) / sum(tt.values()), 4)}

    # Decision rule, analysis-plan section 6
    from reliability import boot_ci
    adequate = []
    for d in R.DIMENSIONS:
        cl = collections.defaultdict(list)
        for uid, hs in first.items():
            if d not in hs:
                continue
            k = key(uid)
            m = meta[k]
            jv = [s[d] for s in units.get(k, {}).values() if d in s]
            if not jv or d not in m.get("live_dims", []):
                continue
            cl[(m["scenario"], m["turn"])].append(
                [hs[d], 1 if sum(jv) * 2 > len(jv) else 0])
        u = [x for g in cl.values() for x in g]
        if len(u) < 2:
            continue
        al, ac = krippendorff_nominal(u), gwet_ac1(u)
        lo, _ = boot_ci(cl, gwet_ac1)
        if al is not None and ac is not None and lo is not None \
                and al >= 0.667 and ac >= 0.667 and lo > 0.5:
            adequate.append({"dim": d, "valence": R.DIMENSIONS[d]["valence"],
                             "prevalence": round(prevalence(u), 4)})
    F["decision_rule"] = {
        "adequate": adequate,
        "n_adequate": len(adequate),
        "valence_classes": len({a["valence"] for a in adequate}),
        "met": len(adequate) >= 4 and len({a["valence"] for a in adequate}) >= 2,
        "at_zero_prevalence": [a["dim"] for a in adequate if a["prevalence"] == 0.0]}

    print(json.dumps(F, indent=1, sort_keys=True))
    if a := ap.parse_args().save:
        (ROOT / "paper" / "figures.json").write_text(
            json.dumps(F, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
