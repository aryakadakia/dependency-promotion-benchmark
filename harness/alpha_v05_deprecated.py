#!/usr/bin/env python3
"""
DEPRECATED -- written against rubric v0.5. Superseded by reliability.py.

Kept only for reference. It reports two dimensions that no longer exist, omits the
six added since, applies the ORDINAL metric to binary data, pools live and
precondition-absent turns into one figure, and does not exclude flagged turns.
Every one of those biases the result in the flattering direction. Do not run it.

Krippendorff's alpha for the scoring dimensions.

Two questions, and they are different:
  RELIABILITY — do the LLM judges agree with each other?
  VALIDITY    — do the judges agree with a human?

High reliability with low validity means the judges share a bias. Both are reported
separately, per dimension, because a rubric can be reliable on one dimension and
useless on another and a single pooled figure would hide that.

Ordinal metric (scores are 0 < 1 < 2, and 0-vs-2 is a worse disagreement than 0-vs-1).

    python alpha.py                                  # judges only
    python alpha.py --human ../runs/handcoded.json   # judges + human validity
"""

import argparse
import json
import pathlib
from collections import defaultdict
from itertools import combinations

import rubric

# Conventional thresholds (Krippendorff 2004): >=0.800 good, >=0.667 tentative.
GOOD, TENTATIVE = 0.800, 0.667


def krippendorff_ordinal(units):
    """
    units: list of lists of observed values (one inner list per unit).
    Units with fewer than 2 ratings contribute nothing and are dropped.
    Returns alpha, or None if undefined.
    """
    units = [u for u in units if len(u) >= 2]
    if len(units) < 2:
        return None

    values = sorted({v for u in units for v in u})
    if len(values) < 2:
        return 1.0            # everyone used one value; no disagreement possible

    idx = {v: i for i, v in enumerate(values)}

    # coincidence matrix
    coinc = defaultdict(float)
    for u in units:
        m = len(u)
        for a, b in combinations(range(m), 2):
            for x, y in ((u[a], u[b]), (u[b], u[a])):
                coinc[(idx[x], idx[y])] += 1.0 / (m - 1)

    n_v = [sum(coinc[(i, j)] for j in range(len(values))) for i in range(len(values))]
    n_total = sum(n_v)
    if n_total <= 1:
        return None

    def delta2(c, k):
        """Ordinal difference: squared distance through the cumulative distribution."""
        lo, hi = min(c, k), max(c, k)
        s = sum(n_v[g] for g in range(lo, hi + 1))
        return (s - (n_v[c] + n_v[k]) / 2.0) ** 2

    Do = sum(coinc[(c, k)] * delta2(c, k)
             for c in range(len(values)) for k in range(len(values))) / n_total
    De = sum(n_v[c] * n_v[k] * delta2(c, k)
             for c in range(len(values)) for k in range(len(values))) / (n_total * (n_total - 1))
    if De == 0:
        return 1.0
    return 1.0 - Do / De


def band(a):
    if a is None:
        return "n/a"
    if a >= GOOD:
        return "good"
    if a >= TENTATIVE:
        return "tentative"
    return "UNRELIABLE"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--judged", default="../runs/judged.json")
    ap.add_argument("--human", default=None, help="handcoded.json from handcode.py")
    ap.add_argument("--human2", default=None, help="a second human coder's scores (uid->dim->score)")
    args = ap.parse_args()

    rows = json.load(open(args.judged))
    print(f"{len(rows)} judged turns\n")

    # ---- inter-judge reliability ----
    print("INTER-JUDGE RELIABILITY  (do the judges agree with each other?)")
    print(f"{'dim':<7}{'alpha':>8}   {'units':>6}  band")
    print("-" * 46)
    judge_units = defaultdict(list)
    for r in rows:
        for dim in rubric.DIMENSIONS:
            vals = [s[dim] for s in r["judges"].values() if dim in s]
            if len(vals) >= 2:
                judge_units[dim].append(vals)
    for dim in rubric.DIMENSIONS:
        a = krippendorff_ordinal(judge_units[dim])
        astr = f"{a:.3f}" if a is not None else "  n/a"
        print(f"{dim:<7}{astr:>8}   {len(judge_units[dim]):>6}  {band(a)}")

    # ---- judge vs human validity ----
    if args.human and pathlib.Path(args.human).exists():
        state = json.load(open(args.human))
        human = state.get("scores", state)
        print(f"\n\nJUDGE-vs-HUMAN VALIDITY  ({len(human)} human-coded items)")
        print("Consensus = median of judge scores for that turn.")
        print(f"{'dim':<7}{'alpha':>8}   {'units':>6}  band")
        print("-" * 46)
        by_uid = {f"{r['scenario']}|{r['model']}|{r['condition']}|{r['sample']}|{r['turn']}": r
                  for r in rows}
        val_units = defaultdict(list)
        matched = 0
        for uid, hs in human.items():
            r = by_uid.get(uid)
            if not r:
                continue
            matched += 1
            for dim, hv in hs.items():
                jv = [s[dim] for s in r["judges"].values() if dim in s]
                if jv:
                    val_units[dim].append([hv, sorted(jv)[len(jv) // 2]])
        for dim in rubric.DIMENSIONS:
            if not val_units[dim]:
                continue
            a = krippendorff_ordinal(val_units[dim])
            astr = f"{a:.3f}" if a is not None else "  n/a"
            print(f"{dim:<7}{astr:>8}   {len(val_units[dim]):>6}  {band(a)}")
        print(f"\n{matched}/{len(human)} human items matched to judged turns.")
        if matched < len(human):
            print("Unmatched items mean the human pool and the judged set diverged — "
                  "check that judge.py covered every run file.")

    # ---- human vs human ----
    if args.human and args.human2 and pathlib.Path(args.human2).exists():
        h1 = json.load(open(args.human)).get("scores", {})
        h2 = json.load(open(args.human2))
        h2 = h2.get("scores", h2)
        shared = set(h1) & set(h2)
        print(f"\n\nHUMAN-vs-HUMAN RELIABILITY  ({len(shared)} shared items)")
        print(f"{'dim':<7}{'alpha':>8}   {'units':>6}  band")
        print("-" * 46)
        for dim in rubric.DIMENSIONS:
            units = [[h1[u][dim], h2[u][dim]] for u in shared
                     if dim in h1.get(u, {}) and dim in h2.get(u, {})]
            if not units:
                continue
            a = krippendorff_ordinal(units)
            astr = f"{a:.3f}" if a is not None else "  n/a"
            print(f"{dim:<7}{astr:>8}   {len(units):>6}  {band(a)}")

    print(f"\nThresholds: >={GOOD} good, >={TENTATIVE} tentative, below that UNRELIABLE.")
    print("Dimensions below threshold are REPORTED as unreliable, not dropped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
