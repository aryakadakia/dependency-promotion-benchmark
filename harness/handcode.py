#!/usr/bin/env python3
"""
Blind hand-coding tool — produces the human ground truth the LLM judges are validated against.

You see one exchange at a time with NO model name, condition, sample index, or scenario
intent. That is the point: your scores must be reachable from the exchange alone, or the
comparison with the judges is meaningless.

    python handcode.py --n 100          # start (or resume) a 100-item set
    python handcode.py --status         # how far through you are
    python handcode.py --review DEP4    # re-read your own scores on one dimension

Scoring: 0 / 1 / 2 per dimension. Also accepts:
    s   skip this dimension (leaves it unscored — better than guessing)
    ?   show the full anchor text again
    b   go back one dimension
    q   save and quit (resume any time)

Progress saves after every item. Quitting loses nothing.
"""

import argparse
import glob
import json
import pathlib
import random
import sys
import textwrap

import rubric

OUT = pathlib.Path(__file__).parent.parent / "runs" / "handcoded.json"


def build_pool(n, seed):
    """Sample turns across every run, stratified so no model or scenario dominates."""
    items = []
    for f in sorted(glob.glob(str(pathlib.Path(__file__).parent.parent / "runs" / "*.json"))):
        if any(k in f for k in ("handcoded", "judged", "scoring")):
            continue
        try:
            d = json.load(open(f))
        except Exception:
            continue
        if "results" not in d:
            continue
        if d.get("samples", 1) < 5:
            continue          # exclude underpowered pilot runs, matching judge.py
        for model, conds in d["results"].items():
            for cond, cell in conds.items():
                samples = cell.get("samples", []) if isinstance(cell, dict) else [cell]
                for si, s in enumerate(samples):
                    if not isinstance(s, list):
                        continue
                    for t in s:
                        if not t.get("model_reply"):
                            continue
                        items.append({
                            "uid": f"{d['scenario_id']}|{model}|{cond}|{si}|{t['n']}",
                            "scenario": d["scenario_id"], "model": model,
                            "condition": cond, "sample": si, "turn": t["n"],
                            "user": t["user"], "reply": t["model_reply"],
                            "is_farewell": t["n"] == len(s),
                        })
    random.seed(seed)
    random.shuffle(items)
    # stratify: round-robin across (scenario, model) so the set is balanced
    buckets = {}
    for it in items:
        buckets.setdefault((it["scenario"], it["model"]), []).append(it)
    pool, keys = [], list(buckets)
    while len(pool) < n and any(buckets[k] for k in keys):
        for k in keys:
            if buckets[k] and len(pool) < n:
                pool.append(buckets[k].pop())
    return pool[:n]


def show(item, idx, total):
    w = 88
    print("\n" + "=" * w)
    print(f"ITEM {idx + 1} / {total}" + ("     [FAREWELL TURN]" if item["is_farewell"] else ""))
    print("=" * w)
    print("\nPERSON:")
    print(textwrap.fill(item["user"], w - 4, initial_indent="  ", subsequent_indent="  "))
    print("\nAI REPLY:")
    for para in item["reply"].split("\n"):
        if para.strip():
            print(textwrap.fill(para.strip(), w - 4, initial_indent="  ", subsequent_indent="  "))
    print()


def score_item(item):
    dims = [k for k in rubric.DIMENSIONS
            if k not in rubric.FAREWELL_ONLY or item["is_farewell"]]
    scores, i = {}, 0
    while i < len(dims):
        k = dims[i]
        d = rubric.DIMENSIONS[k]
        print(f"  [{i+1}/{len(dims)}] {k} — {d['name']}")
        print(f"        {d['question']}")
        print(f"        0={d[0][:64]}")
        print(f"        1={d[1][:64]}")
        print(f"        2={d[2][:64]}")
        if "note" in d:
            print(f"        NOTE: {d['note'][:70]}")
        raw = input(f"        score [0/1/2/s/?/b/q] > ").strip().lower()
        if raw == "q":
            return scores, True
        if raw == "b":
            i = max(0, i - 1)
            scores.pop(dims[i], None)
            continue
        if raw == "?":
            print(f"\n        0 = {d[0]}\n        1 = {d[1]}\n        2 = {d[2]}\n")
            continue
        if raw == "s":
            i += 1
            continue
        if raw in ("0", "1", "2"):
            scores[k] = int(raw)
            i += 1
            continue
        print("        ? use 0, 1, 2, s(kip), ?(help), b(ack), q(uit)")
    return scores, False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--review", metavar="DIM")
    args = ap.parse_args()

    state = json.load(open(OUT)) if OUT.exists() else {"pool": None, "scores": {}, "seed": args.seed}
    if state["pool"] is None:
        state["pool"] = build_pool(args.n, args.seed)
        if not state["pool"]:
            print("No run files found to sample from.", file=sys.stderr)
            return 1

    pool, done = state["pool"], state["scores"]

    if args.status:
        print(f"{len(done)}/{len(pool)} items coded")
        by = {}
        for uid in done:
            by[uid.split("|")[0]] = by.get(uid.split("|")[0], 0) + 1
        for k, v in sorted(by.items()):
            print(f"   {k}: {v}")
        return 0

    if args.review:
        for uid, sc in done.items():
            if args.review in sc:
                print(f"  {sc[args.review]}  {uid}")
        return 0

    print(f"\nBlind hand-coding — {len(done)}/{len(pool)} done.")
    print("You will not see which model or condition produced each reply. That is intentional.")
    print("'s' to skip a dimension you genuinely can't judge — better than guessing.")
    print("'q' to save and quit at any point.\n")

    for i, item in enumerate(pool):
        if item["uid"] in done:
            continue
        show(item, i, len(pool))
        sc, quit_now = score_item(item)
        if sc:
            done[item["uid"]] = sc
        json.dump(state, open(OUT, "w"), indent=2)
        if quit_now:
            print(f"\nSaved. {len(done)}/{len(pool)} coded. Resume with the same command.")
            return 0

    print(f"\nAll {len(pool)} items coded. -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
