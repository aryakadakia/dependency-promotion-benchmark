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
import rubric_v07
from build_frame import balanced_take

RUB = rubric_v07   # set from --rubric in main()
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
        if not r.get("human_code") or r.get("invalid_reason"):
            continue
        pool.append({
            "uid": f"{r['scenario']}|{r['model']}|{r['condition']}|{r['sample']}|{r['turn']}",
            "scenario": r["scenario"], "model": r["model"],
            "condition": r["condition"], "sample": r["sample"], "turn": r["turn"],
            "user": r["user"], "reply": r["reply"], "prior": r.get("prior", ""),
            "is_farewell": r["is_farewell"],
            "live_dims": r.get("live_dims", []),
            "human_dims": r.get("human_dims"),
            "stratum": r.get("stratum", "live"),
        })
    random.seed(fr.get("seed", 0))
    random.shuffle(pool)
    return pool


def build_recode(pool, n, rng):
    """
    Duplicate n already-selected turns onto the END of the pool.

    Gives intra-rater reliability: if the same person answers the same turn two
    different ways, the construct is ambiguous to humans -- which is evidence that
    low judge-human agreement reflects the construct rather than the judges, and
    that distinction is the whole point of collecting human scores at all.

    Appended rather than interleaved so as much of the run as possible separates
    the two viewings. A gap of days is better than a gap of hours; if the tail is
    coded in a later sitting the estimate is stronger, but it is informative either
    way as long as the coder is not shown their earlier answer -- and they are not.
    """
    sel = balanced_take(pool, n, rng)
    out = []
    for it in sel:
        d = dict(it)
        d["recode_of"] = it["uid"]
        d["uid"] = it["uid"] + "#recode"
        out.append(d)
    return out


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
    # The frame states exactly what to ask this coder: gated dimensions, the
    # ungated pair on a subsample, and a spot check on background turns. Recomputing
    # it here would diverge from what the workbook asks.
    if item.get("human_dims") is not None:
        return [k for k in item["human_dims"] if k in RUB.DIMENSIONS
                and (k not in RUB.FAREWELL_ONLY or item["is_farewell"])]
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


def score_item(item, rng, asked=None):
    # A turn must always put the SAME questions, whichever way it is reached.
    # Background turns draw 3 dimensions from a shared RNG, so recomputing on a
    # revisit silently changes the question set -- which breaks both the back
    # navigation and the recode comparison.
    prior = None
    if asked is not None:
        prior = asked.get(item["uid"]) or asked.get(item.get("recode_of"))
    dims = prior if prior else dims_to_ask(item, rng)
    if asked is not None:
        asked[item["uid"]] = dims
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
        back = "b=prev turn" if i == 0 else "b=back"
        raw = input(f"      present? [1=yes/0=no/s/?/{back}/q] > ").strip().lower()
        if raw == "q":
            return scores, "quit"
        if raw == "b":
            if i == 0:
                return scores, "back"      # step back to the previous TURN
            i -= 1
            scores.pop(dims[i], None)
            scores.pop(dims[i] + "_init", None)
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
    return scores, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--review", metavar="DIM")
    ap.add_argument("--rubric", default="v07", choices=["v05", "v06", "v07"])
    ap.add_argument("--recode", type=int, default=25,
                    help="turns repeated at the END of the pool for intra-rater "
                         "reliability. You are never shown your earlier answer.")
    args = ap.parse_args()

    global RUB
    RUB = {"v05": rubric, "v06": rubric_v06, "v07": rubric_v07}[args.rubric]
    rng = random.Random(args.seed)
    state = json.load(open(OUT)) if OUT.exists() else {"pool": None, "scores": {}, "seed": args.seed}
    if state["pool"] is None:
        base = build_pool()
        state["pool"] = base + build_recode(base, args.recode, random.Random(args.seed))
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
    print("'b' on the first question of a turn goes BACK to the previous turn.")
    n_re = sum(1 for it in pool if it.get("recode_of"))
    if n_re:
        print(f"The last {n_re} turns are deliberate repeats. Answer them as you find")
        print("them — you are not shown what you said before, and differing is fine.")
    print("'q' to save and quit at any point.\n")

    asked = state.setdefault("asked", {})
    i = 0
    while i < len(pool):
        item = pool[i]
        if item["uid"] in done:
            i += 1
            continue
        show(item, i, len(pool))
        sc, action = score_item(item, rng, asked)
        if sc:
            done[item["uid"]] = sc
        json.dump(state, open(OUT, "w"), indent=2)
        if action == "quit":
            print(f"\nSaved. {len(done)}/{len(pool)} coded. Resume with the same command.")
            return 0
        if action == "back":
            # Re-open the previous turn for editing. Its stored answers are dropped
            # so it is re-asked cleanly rather than half-overwritten.
            j = i - 1
            while j >= 0 and pool[j]["uid"] not in done:
                j -= 1
            if j < 0:
                print("  (already at the first turn)")
                continue
            done.pop(pool[j]["uid"], None)
            json.dump(state, open(OUT, "w"), indent=2)
            i = j
            continue
        i += 1

    print(f"\nAll {len(pool)} items coded. -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
