#!/usr/bin/env python3
"""
Blind hand-coding tool — produces the human ground truth the LLM judges are validated against.

You see one exchange at a time with NO model name, condition, sample index, or scenario
intent. That is the point: your scores must be reachable from the exchange alone, or the
comparison with the judges is meaningless.

    python handcode.py                  # start (or resume) the frame's human subset
    python handcode.py --status         # how far through you are
    python handcode.py --review DEP4    # re-read your own scores on one dimension

Items come from runs/frame.json -- the SAME turns the LLM judges score, in the same
order of information. Sampling independently here would produce a human set and a
judge set that do not overlap, and nothing could be compared.

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
import rubric_v06

RUB = rubric_v06   # set from --rubric in main()
OUT = pathlib.Path(__file__).parent.parent / "runs" / "handcoded.json"
FRAME = pathlib.Path(__file__).parent.parent / "runs" / "frame.json"


def _farewell_turns():
    out = {}
    for f in glob.glob(str(pathlib.Path(__file__).parent.parent / "scenarios" / "*.json")):
        d = json.load(open(f))
        out[d["id"]] = max(t["n"] for t in d["turns"])
    return out


def build_pool(_n=None, _seed=None):
    """
    The human-coding subset of the shared sampling frame.

    Deliberately NOT an independent sample. An earlier version drew its own
    stratified sample from the run files, which would have produced human scores on
    turns no judge scored -- zero overlap, nothing comparable.
    """
    if not FRAME.exists():
        raise SystemExit(f"No frame at {FRAME}. Run:  python build_frame.py")
    fr = json.load(open(FRAME))
    pool = []
    for r in fr["turns"]:
        if not r.get("human_code"):
            continue
        pool.append({
            "uid": f"{r['scenario']}|{r['model']}|{r['condition']}|{r['sample']}|{r['turn']}",
            "scenario": r["scenario"], "model": r["model"],
            "condition": r["condition"], "sample": r["sample"], "turn": r["turn"],
            "user": r["user"], "reply": r["reply"], "prior": r.get("prior", ""),
            "is_farewell": r["is_farewell"],
            "live_dims": r.get("live_dims", []),
            "stratum": r.get("stratum", "live"),
        })
    random.seed(fr.get("seed", 0))
    random.shuffle(pool)
    return pool


def dims_to_ask(item, rng):
    """
    Which dimensions to put to the coder for this turn.

    Gated on the author's own `probes` annotation. Asking all 12 dimensions on every
    turn is what made the judge numbers meaningless -- most dimensions were scored on
    turns where they could not have occurred, and agreeing that an absent thing is
    absent is free. It is also the difference between ~1,200 judgements and ~300,
    which is the difference between a task that gets finished and one that does not.

    On background turns (nothing live) a small random subset is still asked, so the
    false-positive rate stays measurable.
    """
    live = [k for k in item["live_dims"] if k in RUB.DIMENSIONS]
    live = [k for k in live if k not in RUB.FAREWELL_ONLY or item["is_farewell"]]
    if live:
        return live
    cands = [k for k in RUB.DIMENSIONS
             if k not in RUB.FAREWELL_ONLY or item["is_farewell"]]
    return sorted(rng.sample(cands, min(3, len(cands))))


def show(item, idx, total):
    w = 88
    print("\n" + "=" * w)
    print(f"ITEM {idx + 1} / {total}" + ("     [FAREWELL TURN]" if item["is_farewell"] else ""))
    print("=" * w)
    # The judges are given the two preceding turns. Withholding them here would
    # handicap the human on exactly the dimensions that ask what a reply does to
    # something already live in the conversation -- DEP1, DEP4, DEP6 -- and any gap
    # would then be misread as a human/LLM difference rather than an information one.
    if item.get("prior"):
        print("\nEARLIER IN THE CONVERSATION:")
        for line in item["prior"].split("\n"):
            if line.strip():
                print(textwrap.fill(line.strip(), w - 6, initial_indent="    ",
                                    subsequent_indent="      "))
    print("\nPERSON:")
    print(textwrap.fill(item["user"], w - 4, initial_indent="  ", subsequent_indent="  "))
    print("\nAI REPLY:")
    for para in item["reply"].split("\n"):
        if para.strip():
            print(textwrap.fill(para.strip(), w - 4, initial_indent="  ", subsequent_indent="  "))
    print()


def score_item(item, rng):
    dims = dims_to_ask(item, rng)
    if item["stratum"] == "background":
        print("  (no dimension marked live here — spot-check only)")
    scores, i = {}, 0
    while i < len(dims):
        k = dims[i]
        d = RUB.DIMENSIONS[k]
        print(f"  [{i+1}/{len(dims)}] {k} — {d['name']}")
        print(f"      {d['question']}")
        print("      YES if:  " + "; ".join(d["counts"][:2]))
        print("      NOT:     " + "; ".join(d["does_not_count"][:2]))
        raw = input("      present? [1=yes/0=no/s/?/b/q] > ").strip().lower()
        if raw == "q":
            return scores, True
        if raw == "b":
            i = max(0, i - 1)
            scores.pop(dims[i], None)
            continue
        if raw == "?":
            print(f"\n      {d['question']}\n")
            print("      YES if any of:")
            for c in d["counts"]:
                print(f"        - {c}")
            print("      These do NOT count:")
            for c in d["does_not_count"]:
                print(f"        - {c}")
            if "note" in d:
                print(f"      NOTE: {d['note']}")
            print()
            continue
        if raw == "s":
            i += 1
            continue
        if raw in ("0", "1"):
            scores[k] = int(raw)
            # Provenance is asked ONLY on a yes, and only where it is meaningful.
            # Bundling it into the score is what made v0.5 level 2 unusable.
            if scores[k] == 1 and d.get("provenance"):
                while True:
                    who = input("        who introduced it? "
                                "[a=assistant/p=person] > ").strip().lower()
                    if who in ("a", "p"):
                        scores[k + "_init"] = ("assistant" if who == "a" else "person")
                        break
            i += 1
            continue
        print("      ? use 1, 0, s(kip), ?(help), b(ack), q(uit)")
    return scores, False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--review", metavar="DIM")
    ap.add_argument("--rubric", default="v06", choices=["v05", "v06"])
    args = ap.parse_args()

    global RUB
    RUB = {"v05": rubric, "v06": rubric_v06}[args.rubric]
    rng = random.Random(args.seed)
    state = json.load(open(OUT)) if OUT.exists() else {"pool": None, "scores": {}, "seed": args.seed}
    if state["pool"] is None:
        state["pool"] = build_pool()
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

    tot = sum(len(dims_to_ask(it, random.Random(args.seed + i)))
              for i, it in enumerate(pool))
    print(f"\nBlind hand-coding ({args.rubric}) — {len(done)}/{len(pool)} items done.")
    print(f"Roughly {tot} yes/no judgements in total — only dimensions the")
    print("scenario marks as live at that turn are put to you.")
    print("You will not see which model or condition produced each reply. That is intentional.")
    print("'s' to skip a dimension you genuinely can't judge — better than guessing.")
    print("'q' to save and quit at any point.\n")

    for i, item in enumerate(pool):
        if item["uid"] in done:
            continue
        show(item, i, len(pool))
        sc, quit_now = score_item(item, rng)
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
