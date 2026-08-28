#!/usr/bin/env python3
"""
Reliability analysis, implementing spec/analysis-plan-v1.md.

Replaces alpha.py, which was written against rubric v0.5: it reported two
dimensions that no longer exist, silently omitted the six added since, applied the
ORDINAL metric to binary data, pooled live and precondition-absent turns into one
figure, and did not exclude the flagged mistral turns. Every one of those makes the
numbers wrong in the flattering direction.

What this reports, per dimension, per population:

  LIVE        turns where the scenario marks the dimension live  -- PRIMARY
  BACKGROUND  turns where nothing is live (false-positive rate)
  POOLED      everything, shown only so the inflation is visible

  n, prevalence, raw agreement, Krippendorff's alpha (NOMINAL -- the data is
  binary), and Gwet's AC1.

AC1 is not decoration. Chance-corrected coefficients collapse toward zero when one
category dominates even at near-perfect observed agreement; this instrument has
already produced 96% raw agreement at alpha = -0.015. Where alpha and AC1 diverge
sharply the reading is "prevalence is extreme", not "raters disagree".

Bootstrap CIs resample AUTHORED TURNS, not generations: the frame draws up to 30
generations from one authored turn, so resampling generations would overstate
precision by roughly the cluster size.

    python reliability.py
    python reliability.py --human ../runs/handcoded.json
"""
import argparse, json, pathlib, random
from collections import defaultdict
import rubric_v07 as R

ROOT = pathlib.Path(__file__).parent.parent
GOOD, TENT = 0.800, 0.667


def _counts(units, cats=(0, 1)):
    """units: list of lists of ratings. Returns per-unit category counts."""
    return [[u.count(c) for c in cats] for u in units]


def raw_agreement(units):
    """Proportion of rater PAIRS within a unit that agree, averaged over units."""
    num = den = 0.0
    for u in units:
        n = len(u)
        if n < 2:
            continue
        for k in set(u):
            c = u.count(k)
            num += c * (c - 1)
        den += n * (n - 1)
    return num / den if den else None


def prevalence(units):
    vals = [v for u in units for v in u]
    return sum(vals) / len(vals) if vals else None


def krippendorff_nominal(units):
    units = [u for u in units if len(u) >= 2]
    if len(units) < 2:
        return None
    vals = sorted({v for u in units for v in u})
    if len(vals) < 2:
        return 1.0
    idx = {v: i for i, v in enumerate(vals)}
    coinc = defaultdict(float)
    for u in units:
        m = len(u)
        for a in range(m):
            for b in range(m):
                if a != b:
                    coinc[(idx[u[a]], idx[u[b]])] += 1.0 / (m - 1)
    n_v = [sum(coinc[(i, j)] for j in range(len(vals))) for i in range(len(vals))]
    n_tot = sum(n_v)
    if n_tot <= 1:
        return None
    Do = sum(coinc[(c, k)] for c in range(len(vals)) for k in range(len(vals)) if c != k) / n_tot
    De = sum(n_v[c] * n_v[k] for c in range(len(vals)) for k in range(len(vals)) if c != k) \
        / (n_tot * (n_tot - 1))
    return 1.0 - Do / De if De else 1.0


def gwet_ac1(units, q=2):
    """AC1 for binary ratings with a variable number of raters per unit."""
    units = [u for u in units if len(u) >= 2]
    if len(units) < 2:
        return None
    cats = (0, 1)
    N = len(units)
    Pa = 0.0
    pi = [0.0] * q
    for u in units:
        n = len(u)
        for j, c in enumerate(cats):
            r = u.count(c)
            Pa += r * (r - 1) / (n * (n - 1))
            pi[j] += r / n
    Pa /= N
    pi = [p / N for p in pi]
    Pe = sum(p * (1 - p) for p in pi) / (q - 1)
    return (Pa - Pe) / (1 - Pe) if Pe != 1 else None


def boot_ci(clusters, fn, B=2000, seed=7):
    """clusters: {authored_turn_key: [units]}. Resamples authored turns."""
    keys = list(clusters)
    if len(keys) < 3:
        return None, None
    rng = random.Random(seed)
    out = []
    for _ in range(B):
        pick = [clusters[keys[rng.randrange(len(keys))]] for _ in keys]
        units = [u for grp in pick for u in grp]
        v = fn(units)
        if v is not None:
            out.append(v)
    if len(out) < B * 0.5:
        return None, None
    out.sort()
    return out[int(0.025 * len(out))], out[int(0.975 * len(out))]


def load(args):
    fr = json.load(open(args.frame))
    meta = {}
    for t in fr["turns"]:
        k = (t["scenario"], t["model"], t["condition"], t["sample"], t["turn"])
        meta[k] = t
    rows = []
    for f in args.judged:
        for r in json.load(open(f)):
            rows.append(r)
    return fr, meta, rows


def collect(rows, meta, judges=None, exclude_invalid=True):
    """(dim, population) -> {authored_turn: [ [ratings], ... ]}"""
    out = defaultdict(lambda: defaultdict(list))
    seen = {}
    for r in rows:
        k = (r["scenario"], r["model"], r["condition"], r["sample"], r["turn"])
        m = meta.get(k)
        if m is None:
            continue
        if exclude_invalid and m.get("invalid_reason"):
            continue
        for j, sc in r["judges"].items():
            if judges and j not in judges:
                continue
            for d, v in sc.items():
                if d.endswith("_init"):
                    continue
                seen.setdefault((k, d), []).append(v)
    for (k, d), vals in seen.items():
        if len(vals) < 2:
            continue
        m = meta[k]
        pop = "LIVE" if d in m.get("live_dims", []) else "BACKGROUND"
        auth = (m["scenario"], m["turn"])
        out[(d, pop)][auth].append(vals)
        out[(d, "POOLED")][auth].append(vals)
    return out


def band(a):
    if a is None:
        return ""
    return "good" if a >= GOOD else "tentative" if a >= TENT else "UNRELIABLE"


def report(data, title, boot=True):
    print(f"\n{'='*96}\n{title}\n{'='*96}")
    print(f"{'dim':<6}{'pop':<12}{'units':>6}{'stim':>6}{'prev':>7}{'agree':>7}"
          f"{'alpha':>8}{'AC1':>8}   {'AC1 95% CI':<18}band")
    print("-"*96)
    for d in R.DIMENSIONS:
        for pop in ("LIVE", "BACKGROUND", "POOLED"):
            cl = data.get((d, pop))
            if not cl:
                continue
            units = [u for grp in cl.values() for u in grp]
            if len(units) < 2:
                continue
            pv, ag = prevalence(units), raw_agreement(units)
            al, ac = krippendorff_nominal(units), gwet_ac1(units)
            lo, hi = boot_ci(cl, gwet_ac1) if (boot and pop == "LIVE") else (None, None)
            ci = f"[{lo:+.2f}, {hi:+.2f}]" if lo is not None else ""
            f = lambda x: f"{x:.3f}" if x is not None else "  n/a"
            print(f"{d:<6}{pop:<12}{len(units):>6}{len(cl):>6}{pv*100:>6.0f}%"
                  f"{ag*100:>6.0f}%{f(al):>8}{f(ac):>8}   {ci:<18}"
                  f"{band(ac) if pop=='LIVE' else ''}")
        print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--judged", nargs="+",
                    default=[str(ROOT/"runs"/"judged_v06_local.json"),
                             str(ROOT/"runs"/"judged_v06_commercial.json")])
    ap.add_argument("--frame", default=str(ROOT/"runs"/"frame.json"))
    ap.add_argument("--human", default=None)
    ap.add_argument("--no-boot", action="store_true")
    args = ap.parse_args()

    fr, meta, rows = load(args)
    n_inv = sum(1 for t in fr["turns"] if t.get("invalid_reason"))
    print(f"frame {fr['n']} turns, rubric {fr.get('rubric')}, "
          f"{n_inv} excluded as invalid")
    judges = sorted({j for r in rows for j in r["judges"]})
    loc = [j for j in judges if j.startswith("ollama")]
    com = [j for j in judges if not j.startswith("ollama")]
    print(f"judges: {len(loc)} local, {len(com)} commercial")

    report(collect(rows, meta), "ALL JUDGES  (primary; LIVE is the estimate that counts)",
           boot=not args.no_boot)
    report(collect(rows, meta, judges=loc), "LOCAL PANEL ONLY", boot=False)
    report(collect(rows, meta, judges=com), "COMMERCIAL PANEL ONLY", boot=False)

    if args.human and pathlib.Path(args.human).exists():
        st = json.load(open(args.human))
        hum = st.get("scores", st)
        print(f"\n{'='*96}\nJUDGE vs HUMAN VALIDITY ({len(hum)} coded turns)\n{'='*96}")
        by = {}
        for r in rows:
            k = f"{r['scenario']}|{r['model']}|{r['condition']}|{r['sample']}|{r['turn']}"
            by.setdefault(k, []).append(r)
        cl = defaultdict(lambda: defaultdict(list))
        for uid, hs in hum.items():
            base = uid.replace("#recode", "")
            for r in by.get(base, []):
                k = (r["scenario"], r["model"], r["condition"], r["sample"], r["turn"])
                m = meta.get(k)
                if not m or m.get("invalid_reason"):
                    continue
                for d, hv in hs.items():
                    if d.endswith("_init"):
                        continue
                    jv = [s[d] for s in r["judges"].values() if d in s]
                    if not jv:
                        continue
                    cons = 1 if sum(jv) * 2 > len(jv) else 0
                    pop = "LIVE" if d in m.get("live_dims", []) else "BACKGROUND"
                    cl[(d, pop)][(m["scenario"], m["turn"])].append([hv, cons])
                    cl[(d, "POOLED")][(m["scenario"], m["turn"])].append([hv, cons])
        report(cl, "HUMAN vs JUDGE-MAJORITY", boot=not args.no_boot)

        # intra-rater, from the recode tail
        pairs = defaultdict(list)
        for uid, hs in hum.items():
            if not uid.endswith("#recode"):
                continue
            first = hum.get(uid.replace("#recode", ""))
            if not first:
                continue
            for d, v in hs.items():
                if not d.endswith("_init") and d in first:
                    pairs[d].append([first[d], v])
        if pairs:
            print(f"\n{'='*96}\nINTRA-RATER (same coder, same turn, second pass)\n{'='*96}")
            print(f"{'dim':<6}{'n':>5}{'agree':>8}{'AC1':>8}")
            for d in R.DIMENSIONS:
                u = pairs.get(d)
                if not u:
                    continue
                ac = gwet_ac1(u)
                print(f"{d:<6}{len(u):>5}{raw_agreement(u)*100:>7.0f}%"
                      f"{(f'{ac:.3f}' if ac is not None else ' n/a'):>8}")
    else:
        print("\n(no hand-coding yet — judge-vs-human and intra-rater sections pending)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
