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
import argparse, json, pathlib, collections, statistics, random, re, sys
import rubric_v07 as R
from reliability import (gwet_ac1, raw_agreement, krippendorff_nominal,
                         prevalence, boot_ci)

ROOT = pathlib.Path(__file__).parent.parent
JUDGED = ["judged_v06_local.json", "judged_v06_commercial.json", "judged_v07_sonnet.json"]


def load():
    fr = json.loads((ROOT / "data" / "frame" / "frame.json").read_text())
    meta = {(t["scenario"], t["model"], t["condition"], t["sample"], t["turn"]): t
            for t in fr["turns"]}
    rows = [r for f in JUDGED for r in json.loads((ROOT / "data" / "judged" / f).read_text())]
    hum = json.loads((ROOT / "data" / "human" / "handcoded.json").read_text())["scores"]
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
    cal = json.loads((ROOT / "data" / "judged" / "calibration.json").read_text())
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

    ug = json.loads((ROOT / "data" / "judged" / "judged_ungated.json").read_text())
    fu = json.loads((ROOT / "data" / "frame" / "frame_ungated.json").read_text())
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

    # --- corpus, context and pilot descriptives ---------------------------
    import glob as _glob, statistics as _st
    cells = {}
    for fn in sorted(_glob.glob(str(ROOT / "data" / "generations" / "SC-*_sp-*_n*.json"))):
        dd = json.loads(pathlib.Path(fn).read_text())
        for mm, conds in dd["results"].items():
            cells[(dd["scenario_id"], dd["system_prompt_id"], mm)] = conds
    by_cond = collections.Counter()
    per_model = collections.Counter()
    for (sid, sp, mm), conds in cells.items():
        for cond, blk in conds.items():
            if isinstance(blk, dict):
                for smp in blk.get("samples", []):
                    by_cond[cond] += len(smp)
                    per_model[mm] += len(smp)
    F["generations"] = {"total": sum(by_cond.values()),
                        "by_condition": dict(by_cond),
                        "measurement_corpus": by_cond["natural"],
                        "probe_and_placebo": sum(v for k, v in by_cond.items()
                                                 if k != "natural"),
                        "per_model": dict(per_model)}

    F["prior_context_chars_median"] = _st.median(
        len(t.get("prior") or "") for t in fr["turns"])

    F["judge_spread"] = round(max(v["ac1"] for v in per.values())
                              - min(v["ac1"] for v in per.values()), 4)
    F["off_gate_human_judgements"] = sum(
        1 for uid, hs in first.items() for d in hs
        if not d.endswith("_init") and d not in R.ALWAYS_LIVE
        and d not in (meta[key(uid)].get("live_dims") or []))

    # Same restriction endearments.py applies: models present at every level.
    EXC = {"ollama:mistral:7b", "google:gemini-3.1-pro-preview"}
    at = collections.defaultdict(set)
    for (sid, sp, mm) in cells:
        if sid == "SC-03" and mm not in EXC:
            at[sp].add(mm)
    common = set.intersection(*at.values()) if len(at) >= 3 else set()
    end_counts = collections.Counter()
    for (sid, sp, mm), conds in cells.items():
        if sid != "SC-03" or mm not in common:
            continue
        for blk in conds.values():
            if isinstance(blk, dict):
                for smp in blk.get("samples", []):
                    end_counts[sp] += len(smp)
    F["endearment"] = {"models": len(common),
                       "replies_per_level": dict(end_counts)}

    # The prior-context truncation the judge pipeline applies, read from the code
    # rather than asserted, since Methods and Limitations both quote it.
    jt = (ROOT / "harness" / "judge.py").read_text()
    m_ = re.search(r"model_reply'\]\[:(\d+)\]", jt) or re.search(r"\[:(\d+)\]", jt)
    F["prior_truncation_chars"] = int(m_.group(1)) if m_ else None

    # System-prompt echo, from the same patterns that set invalid_reason on the
    # frame, so the rate stated in Methods and the exclusion applied to the data
    # come from one definition. Previously these figures were only in
    # echo_report.py's stdout and the number checker passed them by accident: the
    # model-name stripper was swallowing "Mistral 7B ... 809 of" whole.
    import build_frame
    _pat = re.compile("|".join(build_frame.ECHO_PATTERNS), re.I)
    _tot = collections.Counter()
    _hit = collections.Counter()
    _sp_tot = collections.Counter()
    _sp_hit = collections.Counter()
    for f_ in sorted((ROOT / "data" / "generations").glob("SC-*_sp-*_n*.json")):
        d_ = json.loads(f_.read_text())
        sp_ = d_.get("system_prompt_id")
        for model_, conds_ in d_["results"].items():
            for blk_ in conds_.values():
                for smp_ in blk_.get("samples", []):
                    for turn_ in smp_:
                        e_ = bool(_pat.search(turn_.get("model_reply") or ""))
                        _tot[model_] += 1
                        _hit[model_] += e_
                        _sp_tot[(model_, sp_)] += 1
                        _sp_hit[(model_, sp_)] += e_
    _aff = sorted(m for m in _tot if _hit[m])
    F["echo"] = {
        "affected_models": _aff,
        "clean_models": sorted(m for m in _tot if not _hit[m]),
        "by_model": {m: {"generations": _tot[m], "echoes": _hit[m],
                         "rate": round(_hit[m] / _tot[m], 4)} for m in _aff},
        "by_prompt": {m: {lv: round(_sp_hit[(m, lv)] / _sp_tot[(m, lv)], 4)
                          for lv in ("neutral", "warm", "retention")
                          if _sp_tot[(m, lv)]} for m in _aff},
        "frame_turns_flagged": sum(1 for t_ in fr["turns"] if t_.get("invalid_reason")),
        "frame_turns_kept_from_affected": sum(
            1 for t_ in fr["turns"]
            if t_["model"] in _aff and not t_.get("invalid_reason"))}

    pilot = json.loads((ROOT / "data" / "judged" / "judged_pilot.json").read_text())
    PJ = sorted({j for r in pilot for j in r["judges"]})
    both = [r for r in pilot if all(j in r["judges"] and r["judges"][j] for j in PJ)]
    u3 = [[r["judges"][j]["PER3"] for j in PJ] for r in both
          if all("PER3" in r["judges"][j] for j in PJ)]
    F["pilot"] = {"both_judged_turns": len(both),
                  "per3_alpha": round(krippendorff_nominal(u3), 4) if len(u3) > 1 else None,
                  "per3_agreement": round(raw_agreement(u3), 4) if len(u3) > 1 else None}

    # --- the second coder -------------------------------------------------
    # The packet's turns are a subset of the primary coder's, restricted to the six
    # contested dimensions, so most judgements here have three raters: the two
    # humans and the six-judge majority. The three pairwise coefficients are
    # computed on the SAME units -- those where all three have a value and the
    # dimension is live -- because the comparison that matters is paired, and a
    # coefficient computed on different support is not comparable to the one beside
    # it in the same table. The two-human figure is also reported on every paired
    # human judgement, including the few turns the judges did not cover.
    pk = json.loads((ROOT / "data" / "human" / "second_coder_key.json").read_text())
    F["second_coder_packet"] = {"turns": len(pk),
                                "questions": sum(len(e["dims"]) for e in pk)}
    scf = ROOT / "data" / "human" / "second_coded.json"
    if scf.exists():
        sc = json.loads(scf.read_text())
        pairs, trip = [], []
        for uid, s2 in sc["scores"].items():
            if not ok(uid):
                continue
            k = key(uid)
            live = meta[k].get("live_dims", [])
            for d, v in s2.items():
                if d.endswith("_init") or d not in live:
                    continue
                h1 = first.get(uid, {}).get(d)
                if h1 is None:
                    continue
                pairs.append((k, d, h1, v))
                jv = [s[d] for s in units.get(k, {}).values() if d in s]
                if jv:
                    trip.append((k, d, h1, v, 1 if sum(jv) * 2 > len(jv) else 0))

        def clust(items, ia, ib):
            c = collections.defaultdict(list)
            for it in items:
                c[(it[0][0], it[0][4])].append([it[ia], it[ib]])
            return c

        def pairstats(items, ia, ib):
            u = [[it[ia], it[ib]] for it in items]
            lo, hi = boot_ci(clust(items, ia, ib), gwet_ac1)
            a_only = sum(1 for it in items if it[ia] == 1 and it[ib] == 0)
            b_only = sum(1 for it in items if it[ia] == 0 and it[ib] == 1)
            return {"n": len(u),
                    "agreement": round(raw_agreement(u), 4),
                    "alpha": round(krippendorff_nominal(u), 4),
                    "ac1": round(gwet_ac1(u), 4),
                    "ac1_ci": [round(lo, 4), round(hi, 4)],
                    "a_only_present": a_only, "b_only_present": b_only}

        vals2 = [v for s in sc["scores"].values()
                 for d, v in s.items() if not d.endswith("_init")]
        F["second_coder"] = {
            "source": sc["source"], "turns": sc["turns"], "questions": sc["questions"],
            "skipped": len(sc["skipped"]), "notes": len(sc["notes"]),
            "notes_on_present": sum(1 for n in sc["notes"] if n["answer"] == "1"),
            "notes_quoting_the_reply": sum(1 for n in sc["notes"]
                                           if n["note"].lstrip().startswith('"')),
            "provenance_blank_on_yes": len(sc["provenance_blank_on_yes"]),
            "judgements_of_presence": sum(
                v for s in sc["scores"].values()
                for d, v in s.items() if not d.endswith("_init")),
            "coded": len(vals2), "prevalence_as_returned": round(sum(vals2) / len(vals2), 4),
            "paired_with_primary": len(pairs),
            "turns_contributing": len({p[0] for p in pairs}),
            "off_live": len([1 for s in sc["scores"].values() for d in s
                             if not d.endswith("_init")]) - len(pairs),
            "authored_turns": len({(p[0][0], p[0][4]) for p in pairs})}
        F["human_human"] = pairstats(pairs, 2, 3)
        F["human_human"]["prevalence_primary"] = round(
            sum(p[2] for p in pairs) / len(pairs), 4)
        F["human_human"]["prevalence_second"] = round(
            sum(p[3] for p in pairs) / len(pairs), 4)

        # The common-support, three-rater comparison.
        F["three_rater"] = {
            "n": len(trip),
            "authored_turns": len({(t[0][0], t[0][4]) for t in trip}),
            "prevalence_primary": round(sum(t[2] for t in trip) / len(trip), 4),
            "prevalence_second": round(sum(t[3] for t in trip) / len(trip), 4),
            "prevalence_judges": round(sum(t[4] for t in trip) / len(trip), 4),
            "agreement": round(raw_agreement([[t[2], t[3], t[4]] for t in trip]), 4),
            "alpha": round(krippendorff_nominal([[t[2], t[3], t[4]] for t in trip]), 4),
            "ac1": round(gwet_ac1([[t[2], t[3], t[4]] for t in trip]), 4),
            "primary_vs_second": pairstats(trip, 2, 3),
            "primary_vs_judges": pairstats(trip, 2, 4),
            "second_vs_judges": pairstats(trip, 3, 4)}

        # Does the second coder agree with the judges BETTER than the primary coder
        # does? The two coefficients share their units, so the difference is
        # bootstrapped as a paired quantity over authored turns rather than read off
        # the overlap of two separate intervals.
        cl3 = collections.defaultdict(list)
        for t in trip:
            cl3[(t[0][0], t[0][4])].append(t)
        ck = list(cl3)
        rng_ = random.Random(7)
        diffs = []
        for _ in range(2000):
            pick = [x for _ in ck for x in cl3[ck[rng_.randrange(len(ck))]]]
            x1 = gwet_ac1([[p[3], p[4]] for p in pick])
            x0 = gwet_ac1([[p[2], p[4]] for p in pick])
            if x1 is not None and x0 is not None:
                diffs.append(x1 - x0)
        diffs.sort()
        F["three_rater"]["second_minus_primary_ac1"] = {
            "point": round(F["three_rater"]["second_vs_judges"]["ac1"]
                           - F["three_rater"]["primary_vs_judges"]["ac1"], 4),
            "ci": [round(diffs[int(0.025 * len(diffs))], 4),
                   round(diffs[int(0.975 * len(diffs))], 4)],
            "p_above_zero": round(sum(1 for v in diffs if v > 0) / len(diffs), 4),
            "resamples": len(diffs)}

        # Ordered by how many units the dimension contributes, not by the
        # contested list: DEP3 is in the packet because its disagreements run 7:0 in
        # one direction, not because its AC1 fell below threshold, so iterating
        # F["contested_dimensions"] would silently drop it.
        byd = {}
        # (-n, name): the dimension name breaks ties, because set iteration order
        # over strings is not stable between interpreter runs and two dimensions
        # here carry the same n. Without it figures.json is not reproducible.
        order = sorted({t[1] for t in trip},
                       key=lambda d: (-sum(1 for t in trip if t[1] == d), d))
        for d in order:
            sub = [t for t in trip if t[1] == d]
            if len(sub) < 2:
                byd[d] = {"n": len(sub)}
                continue
            byd[d] = {
                "n": len(sub),
                "prevalence_primary": round(sum(t[2] for t in sub) / len(sub), 4),
                "prevalence_second": round(sum(t[3] for t in sub) / len(sub), 4),
                "prevalence_judges": round(sum(t[4] for t in sub) / len(sub), 4),
                "primary_vs_judges_ac1": round(gwet_ac1([[t[2], t[4]] for t in sub]), 4),
                "second_vs_judges_ac1": round(gwet_ac1([[t[3], t[4]] for t in sub]), 4),
                "primary_vs_second_ac1": round(gwet_ac1([[t[2], t[3]] for t in sub]), 4),
                "second_minus_primary_ac1": round(
                    gwet_ac1([[t[3], t[4]] for t in sub])
                    - gwet_ac1([[t[2], t[4]] for t in sub]), 4)}
        # Per judge, against BOTH coders, on the same units. Table 10 orders the
        # judges against the first coder across all sixteen dimensions; this asks
        # whether that ordering survives a change of human referent, holding the
        # units fixed. It does not, which bears on Section 4.5's claim.
        pj = {}
        for j in sorted({j for u in units.values() for j in u}):
            sub = [t for t in trip if j in {jj for jj in units.get(t[0], {})}
                   and t[1] in units[t[0]].get(j, {})]
            if len(sub) < 2:
                continue
            a = [[t[3], units[t[0]][j][t[1]]] for t in sub]
            b = [[t[2], units[t[0]][j][t[1]]] for t in sub]
            pj[j] = {"n": len(sub),
                     "second_agreement": round(raw_agreement(a), 4),
                     "second_ac1": round(gwet_ac1(a), 4),
                     "primary_agreement": round(raw_agreement(b), 4),
                     "primary_ac1": round(gwet_ac1(b), 4)}
        F["three_rater"]["per_judge"] = pj
        F["three_rater"]["mean_per_judge_second_ac1"] = round(
            statistics.mean(v["second_ac1"] for v in pj.values()), 3)
        F["three_rater"]["mean_per_judge_primary_ac1"] = round(
            statistics.mean(v["primary_ac1"] for v in pj.values()), 3)
        F["three_rater"]["best_judge_against_second"] = max(
            pj, key=lambda j: pj[j]["second_ac1"])
        F["three_rater"]["best_judge_against_primary"] = max(
            pj, key=lambda j: pj[j]["primary_ac1"])

        # Judge-judge agreement on the same units, for the ensemble comparison:
        # the majority is a better match to the second coder than its members are.
        jj = []
        jl = sorted(pj)
        for i, x in enumerate(jl):
            for y in jl[i + 1:]:
                sub = [[units[t[0]][x][t[1]], units[t[0]][y][t[1]]] for t in trip
                       if t[1] in units[t[0]].get(x, {})
                       and t[1] in units[t[0]].get(y, {})]
                if len(sub) >= 2:
                    jj.append(gwet_ac1(sub))
        F["three_rater"]["judge_judge_pairs"] = len(jj)
        F["three_rater"]["mean_judge_judge_ac1"] = round(statistics.mean(jj), 3)
        F["three_rater"]["judges_closer_to_primary"] = sorted(
            j for j, e in pj.items() if e["primary_ac1"] > e["second_ac1"])
        # Spearman between the two rankings of the same six judges. Reported so
        # that "the ordering does not survive" is a number rather than a reading
        # of two sorted columns.
        def _rank(key):
            s = sorted(pj, key=lambda j: -pj[j][key])
            return {j: i + 1 for i, j in enumerate(s)}
        r1, r2 = _rank("primary_ac1"), _rank("second_ac1")
        n_ = len(pj)
        d2 = sum((r1[j] - r2[j]) ** 2 for j in pj)
        F["three_rater"]["judge_rank_spearman"] = round(
            1 - 6 * d2 / (n_ * (n_ ** 2 - 1)), 3)

        F["three_rater"]["by_dimension"] = byd
        # How much of the result rests on the three dimensions that have enough
        # units to estimate anything. byd is ordered by descending n.
        F["three_rater"]["n_three_largest_dimensions"] = sum(
            e["n"] for e in list(byd.values())[:3])

    print(json.dumps(F, indent=1, sort_keys=True))
    if a := ap.parse_args().save:
        (ROOT / "paper" / "figures.json").write_text(
            json.dumps(F, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
