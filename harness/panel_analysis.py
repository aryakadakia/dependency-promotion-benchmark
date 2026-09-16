#!/usr/bin/env python3
"""
Panel-level analysis: the figures in Results 4.1-4.4 that reliability.py does not
produce -- per-judge validity, judge-judge pairwise agreement, the family and
capability breakdowns, the prevalence/agreement relationship, and the direction of
human-judge disagreement.

reliability.py stays the per-dimension instrument report; this is the per-RATER one.
Both read the same frame, apply the same invalid-turn exclusion, and restrict to
live turns unless stated.

    python panel_analysis.py
"""
import argparse, json, pathlib, statistics
from collections import defaultdict
import rubric_v07 as R
from reliability import gwet_ac1, raw_agreement, prevalence

ROOT = pathlib.Path(__file__).parent.parent
FAMILY = {"ollama:gemma3:12b": "google", "ollama:qwen3:14b": "alibaba",
          "ollama:llama3.1:8b": "meta", "google:gemini-3.7-flash": "google",
          "anthropic:claude-haiku-4-5": "anthropic",
          "anthropic:claude-sonnet-5": "anthropic"}
TIER = {j: ("open" if j.startswith("ollama") else "commercial") for j in FAMILY}


def load(frame, judged, human):
    fr = json.load(open(frame))
    meta = {(t["scenario"], t["model"], t["condition"], t["sample"], t["turn"]): t
            for t in fr["turns"]}
    rows = [r for f in judged for r in json.load(open(f))]
    st = json.load(open(human))
    return fr, meta, rows, st.get("scores", st)


def by_unit(rows):
    out = defaultdict(dict)
    for r in rows:
        k = (r["scenario"], r["model"], r["condition"], r["sample"], r["turn"])
        for j, sc in r["judges"].items():
            out[k].setdefault(j, {}).update(
                {d: v for d, v in sc.items() if not d.endswith("_init")})
    return out


def live_only(meta, k, d):
    m = meta.get(k)
    return bool(m) and not m.get("invalid_reason") and d in m.get("live_dims", [])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frame", default=str(ROOT/"runs"/"frame.json"))
    ap.add_argument("--judged", nargs="+",
                    default=[str(ROOT/"runs"/"judged_v06_local.json"),
                             str(ROOT/"runs"/"judged_v06_commercial.json"),
                             str(ROOT/"runs"/"judged_v07_sonnet.json")])
    ap.add_argument("--human", default=str(ROOT/"runs"/"handcoded.json"))
    a = ap.parse_args()
    fr, meta, rows, hum = load(a.frame, a.judged, a.human)
    units = by_unit(rows)

    def key(uid):
        p = uid.replace("#recode", "").split("|")
        return (p[0], p[1], p[2], int(p[3]), int(p[4]))

    def valid(uid):
        m = meta.get(key(uid))
        return bool(m) and not m.get("invalid_reason")

    first = {u: s for u, s in hum.items()
             if not u.endswith("#recode") and valid(u)}
    dropped = sum(1 for u in hum
                  if not u.endswith("#recode") and not valid(u))
    n_j = sum(len([d for d in s if not d.endswith("_init")]) for s in first.values())
    n_re = sum(1 for u in hum if u.endswith("#recode") and valid(u))
    n_sc = sum(len([d for d in s if not d.endswith("_init")])
               for u, s in hum.items() if u.endswith("#recode") and valid(u))
    print(f"human coding: {len(first)} turns, {n_j} judgements, "
          f"{n_re} blind repeats ({n_sc} judgements); "
          f"{dropped} coded turns dropped as degenerate")
    tot = sum(len(s) for k, js in units.items() if k in meta
              and not meta[k].get("invalid_reason") for s in js.values())
    print(f"machine scoring: {len([k for k in units if k in meta])} turns, "
          f"{len({j for js in units.values() for j in js})} judges, "
          f"{tot} dimension-scores")

    # ---- per-judge vs human, live turns -------------------------------------
    print("\nPER-JUDGE vs HUMAN (live turns)")
    print(f"{'judge':<28}{'tier':<12}{'n':>6}{'agree':>8}{'AC1':>8}")
    per_judge = {}
    for j in sorted(FAMILY):
        u = []
        for uid, hs in first.items():
            k = key(uid)
            sc = units.get(k, {}).get(j)
            if not sc:
                continue
            for d, hv in hs.items():
                if d in sc and live_only(meta, k, d):
                    u.append([hv, sc[d]])
        if len(u) < 2:
            continue
        per_judge[j] = (len(u), raw_agreement(u), gwet_ac1(u))
        print(f"{j:<28}{TIER[j]:<12}{len(u):>6}{per_judge[j][1]*100:>7.0f}%"
              f"{per_judge[j][2]:>8.3f}")

    # ---- pairwise judge-judge ----------------------------------------------
    print("\nPAIRWISE JUDGE-JUDGE (live turns)")
    js = sorted(FAMILY)
    pair = {}
    for i, x in enumerate(js):
        for y in js[i+1:]:
            u = []
            for k, sc in units.items():
                if x not in sc or y not in sc:
                    continue
                for d in set(sc[x]) & set(sc[y]):
                    if live_only(meta, k, d):
                        u.append([sc[x][d], sc[y][d]])
            if len(u) >= 2:
                pair[(x, y)] = gwet_ac1(u)
    for (x, y), v in sorted(pair.items(), key=lambda t: -t[1]):
        print(f"  {x:<26}{y:<26}{v:>7.3f}")
    same = [v for (x, y), v in pair.items() if FAMILY[x] == FAMILY[y]]
    cross = [v for (x, y), v in pair.items() if FAMILY[x] != FAMILY[y]]
    cc = [v for (x, y), v in pair.items() if TIER[x] == TIER[y] == "commercial"]
    oo = [v for (x, y), v in pair.items() if TIER[x] == TIER[y] == "open"]
    m = statistics.mean
    print(f"\n  mean judge-judge          {m(pair.values()):.3f}  (n pairs {len(pair)})")
    print(f"  mean judge-human          {m(v[2] for v in per_judge.values()):.3f}")
    print(f"  same-family {m(same):.3f} (n={len(same)})   "
          f"cross-family {m(cross):.3f} (n={len(cross)})")
    print(f"  commercial-commercial {m(cc):.3f} (n={len(cc)})   "
          f"open-open {m(oo):.3f} (n={len(oo)})")

    # ---- prevalence vs judge-human AC1, per dimension ------------------------
    print("\nPREVALENCE vs JUDGE-HUMAN AC1 (live turns, judge majority)")
    print(f"{'dim':<7}{'n':>5}{'prev':>7}{'agree':>7}{'AC1':>8}")
    pts = []
    for d in R.DIMENSIONS:
        u = []
        for uid, hs in first.items():
            if d not in hs:
                continue
            k = key(uid)
            sc = units.get(k, {})
            jv = [s[d] for s in sc.values() if d in s]
            if not jv or not live_only(meta, k, d):
                continue
            u.append([hs[d], 1 if sum(jv)*2 > len(jv) else 0])
        if len(u) < 2:
            continue
        pv, ac = prevalence(u), gwet_ac1(u)
        pts.append((d, len(u), pv, ac))
        print(f"{d:<7}{len(u):>5}{pv*100:>6.0f}%{raw_agreement(u)*100:>6.0f}%{ac:>8.3f}")
    xs = [abs(p[2]-0.5) for p in pts]
    ys = [p[3] for p in pts]
    mx, my = m(xs), m(ys)
    num = sum((x-mx)*(y-my) for x, y in zip(xs, ys))
    den = (sum((x-mx)**2 for x in xs) * sum((y-my)**2 for y in ys)) ** 0.5
    print(f"\n  r(|prevalence - 0.5|, AC1) = {num/den:.3f} over {len(pts)} dimensions")
    ext = [p for p in pts if p[2] < 0.15 or p[2] > 0.85]
    mid = [p for p in pts if 0.35 <= p[2] <= 0.65]
    print(f"  extreme (<15% or >85%): mean AC1 {m(p[3] for p in ext):.3f}  "
          f"[{', '.join(p[0] for p in ext)}]")
    print(f"  mid (35-65%):           mean AC1 {m(p[3] for p in mid):.3f}  "
          f"[{', '.join(p[0] for p in mid)}]")

    # ---- direction of disagreement ------------------------------------------
    # Contested = judge-human AC1 below the 0.667 tentative threshold.
    contested = [p[0] for p in pts if p[3] < 0.667]
    print("\nDIRECTION OF HUMAN-JUDGE DISAGREEMENT (live turns)")
    print(f"{'dim':<7}{'human 1 / judges 0':>20}{'human 0 / judges 1':>22}")
    hi = lo = 0
    for d, _, pv, _ in sorted(pts, key=lambda p: p[0]):
        a = b = 0
        for uid, hs in first.items():
            if d not in hs:
                continue
            k = key(uid)
            jv = [s[d] for s in units.get(k, {}).values() if d in s]
            if not jv or not live_only(meta, k, d):
                continue
            cons = 1 if sum(jv)*2 > len(jv) else 0
            if hs[d] == 1 and cons == 0:
                a += 1
            elif hs[d] == 0 and cons == 1:
                b += 1
        if a or b:
            print(f"{d:<7}{a:>20}{b:>22}{'  *' if d in contested else ''}")
        if d in contested:
            hi, lo = hi + a, lo + b
    print(f"\n* dimensions with judge-human AC1 below 0.667: "
          f"{hi} / {hi+lo} disagreements run human-present, judges-absent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
