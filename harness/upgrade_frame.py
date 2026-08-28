#!/usr/bin/env python3
"""
Add v0.7's three new dimensions to an existing frame, IN PLACE.

Deliberately not a rebuild. build_frame.py allocates turns per dimension, so running
it against a 16-dimension rubric would draw a different 337 turns -- and every one of
the 1,462 judge scores already collected is keyed to the current set. Those scores
remain valid because v0.6's dimensions are imported unchanged into v0.7; only the
three new dimensions need scoring, on the same turns.

Two audiences, two dimension lists per turn:

  live_dims   what the JUDGES score. DEP7/DEP8 are ungated, so all 337 turns get
              them; judge calls cost fractions of a cent and coverage is free.
  human_dims  what the CODER is asked. The ungated pair is put to them on a seeded,
              model-balanced subsample instead of all 100 turns -- 30-40 live turns
              is ample for a reliability estimate, and asking all 100 would roughly
              double the coding burden for precision nobody needs.
"""
import argparse, json, pathlib, random
from collections import Counter

import rubric_v07 as R
from build_frame import balanced_take

ROOT = pathlib.Path(__file__).parent.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frame", default=str(ROOT / "runs" / "frame.json"))
    ap.add_argument("--human-ungated", type=int, default=45,
                    help="human turns asked the ungated dimensions (DEP7/DEP8)")
    ap.add_argument("--seed", type=int, default=20260828)
    args = ap.parse_args()

    fr = json.load(open(args.frame))
    turns = fr["turns"]
    print(f"frame: {len(turns)} turns, currently rubric {fr.get('rubric')}")

    for t in turns:
        t["live_dims"] = R.live_dims(t.get("all_probes", []), t["is_farewell"])

    human = [t for t in turns if t.get("human_code")]
    rng = random.Random(args.seed)
    ungated_for = {id(t) for t in balanced_take(human, args.human_ungated, rng)}
    for t in turns:
        if not t.get("human_code"):
            t.pop("human_dims", None)
            continue
        d = set(R.gated_dims(t.get("all_probes", []), t["is_farewell"]))
        if id(t) in ungated_for:
            d |= R.ALWAYS_LIVE
            if t["is_farewell"]:
                d.discard("DEP8")
        if not R.gated_dims(t.get("all_probes", []), t["is_farewell"]):
            # Background turn: keep a small spot check of GATED dimensions. Without
            # it the false-positive rate is unmeasured for every gated dimension --
            # we would only ever ask them where the design says they should fire.
            cands = [k for k in R.DIMENSIONS
                     if k not in R.ALWAYS_LIVE
                     and (k not in R.FAREWELL_ONLY or t["is_farewell"])]
            d |= set(random.Random(hash(t["scenario"] + str(t["turn"]) + t["model"])
                                   & 0xFFFFFF).sample(cands, 3))
        t["human_dims"] = sorted(d)

    fr["rubric"] = "v07"
    fr["human_ungated_subsample"] = args.human_ungated
    json.dump(fr, open(args.frame, "w"), indent=2)

    j = Counter(d for t in turns for d in t["live_dims"])
    h = Counter(d for t in turns for d in t.get("human_dims", []))
    print(f"\n{'dim':<7}{'judge turns':>12}{'human':>7}   note")
    for k in R.DIMENSIONS:
        note = "NEW — needs top-up pass" if k in R.NEW_IN_V07 else ""
        print(f"{k:<7}{j[k]:>12}{h[k]:>7}   {note}")
    print(f"\nhuman judgements total: {sum(h.values())} "
          f"(was {sum(len(t.get('human_dims', t['live_dims'])) for t in [])or 234})")
    print(f"judge calls needed for the top-up: "
          f"{sum(1 for t in turns for d in t['live_dims'] if d in R.NEW_IN_V07)} "
          f"dimension-scores per judge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
