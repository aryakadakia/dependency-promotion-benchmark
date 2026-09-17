#!/usr/bin/env python3
"""
Build the fixed turn set that every scoring arm and the human coder will share.

WHY THIS EXISTS
---------------
The first judging pilot sampled turns with `--sample-frac`, i.e. uniformly at
random. That produced a set in which most rubric dimensions were never actually
instantiated: PER3 was live on 5 of 101 turns, DEP2 on 3, and DEP3/PRO3/PRO4 on
none at all. Reliability computed over such a set is dominated by turns where the
construct is ABSENT, and agreeing that an absent thing is absent is free.

Measured on the pilot, agreement splits sharply:

    dim    live turns    not-live turns
    DEP1      24%             67%
    PER3      20%            100%
    PRO2      50%             83%
    DEP2      67% (n=3)       87%

So a pooled figure flatters every dimension, and the flattery is largest exactly
where the construct is rarest. DEP2's headline alpha of 0.899 came from 98 turns
where DEP2 could not have occurred.

The scenarios already record which dimensions are live per turn, in each turn's
`probes` list -- author-side annotation that the judge pipeline never used. This
script uses it to build a frame that oversamples live turns, so each dimension is
measured where it is actually instantiated, with a background stratum retained to
estimate the false-positive rate.

    python build_frame.py --per-dim 24 --background 60 --human 100

Output: data/frame/frame.json  -- the sampling frame, fixed and seeded.
"""

import argparse
import glob
import json
import pathlib
import random
from collections import Counter, defaultdict

import rubric_v06
import rubric_v07

RUB = None
ROOT = pathlib.Path(__file__).parent.parent
GENS = ROOT / "data" / "generations"
FRAME = ROOT / "data" / "frame"
SCEN = ROOT / "scenarios"


# --- degenerate-reply detection ------------------------------------------------
# mistral:7b reproduces the SP-warm system prompt as though the USER had written it,
# then thanks them for it. Such a reply is not a response to the person and cannot be
# scored for relational behaviour.
#
# This MUST run on every frame build and every extension. It was first applied once,
# to a 337-turn frame, and the frame was then extended three times without re-running
# it -- leaving 17 echo turns unflagged, four of which reached the human coding set.
ECHO_PATTERNS = [
    r"thank you (so much )?for your kind words",
    r"thank you,? i appreciate your kind words",
    r"i'?m (really )?(glad|happy) (to (hear|know) )?(that )?you (appreciate|find me|feel i'?m)",
    r"glad (to hear )?(that )?you (appreciate|value) (my|the) (efforts?|warmth|support)",
]


def flag_degenerate(turns):
    """Set invalid_reason on replies that echo the system prompt back as user speech.
    Returns the number newly flagged."""
    import re
    pat = re.compile("|".join(ECHO_PATTERNS), re.I)
    n = 0
    for t in turns:
        if t.get("invalid_reason"):
            continue
        if pat.search(t.get("reply", "")):
            t["invalid_reason"] = "system_prompt_echo"
            t["human_code"] = False
            t.pop("human_dims", None)
            n += 1
    return n


def pick_rubric(name):
    return {"v06": rubric_v06, "v07": rubric_v07}[name]


def load_liveness():
    """(scenario_id, turn_n) -> set of probe labels the author marked live."""
    live, vocab = {}, Counter()
    for f in glob.glob(str(SCEN / "*.json")):
        d = json.load(open(f))
        for t in d["turns"]:
            ps = set(t.get("probes") or [])
            live[(d["id"], t["n"])] = ps
            vocab.update(ps)
    return live, vocab


def load_pool(condition="natural", min_samples=5):
    """Every available generation, with its context. One record per turn."""
    pool = []
    for f in glob.glob(str(GENS / "*.json")):
        try:
            d = json.load(open(f))
        except Exception:
            continue
        if not isinstance(d, dict) or "results" not in d or "scenario_id" not in d:
            continue
        if d.get("samples", 1) < min_samples:
            continue
        sid = d["scenario_id"]
        for model, conds in d["results"].items():
            for cond, cell in conds.items():
                if condition and cond != condition:
                    continue
                samples = cell.get("samples", []) if isinstance(cell, dict) else [cell]
                for si, s_ in enumerate(samples):
                    if not isinstance(s_, list):
                        continue
                    for ti, t in enumerate(s_):
                        pool.append({
                            "scenario": sid, "model": model, "condition": cond,
                            "sample": si, "turn": t["n"],
                            "user": t["user"], "reply": t["model_reply"],
                            "acvrt_state": t.get("acvrt_state"),
                            "is_farewell": t["n"] == max(x["n"] for x in s_),
                            "prior": "\n".join(
                                f"Person: {x['user']}\nAI: {x['model_reply'][:200]}"
                                for x in s_[max(0, ti - 2):ti]),
                            "source_file": pathlib.Path(f).name,
                        })
    return pool


def balanced_take(cands, quota, rng):
    """
    Take `quota` records spread as evenly as possible over models first and
    distinct authored turns second.

    Model balance is the priority because judge drop-out in the pilot was
    model-correlated: replies from different families differ in length and
    ambiguity, so a frame skewed toward one family would confound reply style with
    dimension difficulty.
    """
    by_model = defaultdict(list)
    for c in cands:
        by_model[c["model"]].append(c)
    for m in by_model:
        # within a model, interleave distinct authored turns before repeating one
        by_turn = defaultdict(list)
        for c in by_model[m]:
            by_turn[(c["scenario"], c["turn"])].append(c)
        for k in by_turn:
            rng.shuffle(by_turn[k])
        keys = sorted(by_turn)
        rng.shuffle(keys)
        out, i = [], 0
        while len(out) < len(by_model[m]):
            added = False
            for k in keys:
                if i < len(by_turn[k]):
                    out.append(by_turn[k][i]); added = True
            if not added:
                break
            i += 1
        by_model[m] = out

    models = sorted(by_model)
    rng.shuffle(models)
    picked, idx = [], 0
    while len(picked) < quota:
        added = False
        for m in models:
            if idx < len(by_model[m]) and len(picked) < quota:
                picked.append(by_model[m][idx]); added = True
        if not added:
            break
        idx += 1
    return picked


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-dim", type=int, default=24,
                    help="target live turns per rubric dimension")
    ap.add_argument("--background", type=int, default=60,
                    help="turns live for NO rubric dimension, to estimate the "
                         "false-positive rate")
    ap.add_argument("--human", type=int, default=100,
                    help="size of the subset flagged for human coding")
    ap.add_argument("--condition", default="natural")
    ap.add_argument("--rubric", default="v07", choices=["v06", "v07"])
    ap.add_argument("--seed", type=int, default=20260827)
    ap.add_argument("-o", "--out", default=str(FRAME / "frame.json"))
    args = ap.parse_args()

    global RUB
    RUB = pick_rubric(args.rubric)
    rng = random.Random(args.seed)
    live, vocab = load_liveness()
    print(f"rubric: {args.rubric}  ({len(RUB.DIMENSIONS)} dimensions)")
    pool = load_pool(args.condition)
    print(f"pool: {len(pool)} generations (condition={args.condition})\n")

    # Probe vocabulary and rubric vocabulary have drifted apart; report it rather
    # than silently ignoring labels that cannot be scored.
    known = set(getattr(RUB, "LIVE_MAP", {})) | set(RUB.DIMENSIONS)
    unscoreable = sorted(set(vocab) - known)
    if unscoreable:
        print(f"NOTE probe labels with no rubric dimension: {', '.join(unscoreable)}")
    reachable = {d for ps in vocab for d in
                 (RUB.live_dims({ps}) if hasattr(RUB, "live_dims")
                  else ({ps} & set(RUB.DIMENSIONS)))}
    unprobed = sorted(set(RUB.DIMENSIONS) - reachable)
    if unprobed:
        print(f"NOTE rubric dimensions never marked live: {', '.join(unprobed)}")
    print()

    chosen, seen = {}, set()

    def key(r):
        return (r["scenario"], r["model"], r["condition"], r["sample"], r["turn"])

    def resolve(r):
        """Live dimensions for this turn, under the selected rubric."""
        probes = live.get((r["scenario"], r["turn"]), set())
        if hasattr(RUB, "live_dims"):
            return set(RUB.live_dims(probes, r["is_farewell"]))
        return {p for p in probes if p in RUB.DIMENSIONS}

    print(f"{'dim':<7}{'authored':>9}{'avail':>7}{'taken':>7}  reason")
    for dim in RUB.DIMENSIONS:
        cands = [r for r in pool if dim in resolve(r)]
        authored = len({(c["scenario"], c["turn"]) for c in cands})
        take = balanced_take(cands, args.per_dim, rng)
        for r in take:
            if key(r) not in seen:
                seen.add(key(r)); chosen[key(r)] = r
        note = "" if len(take) >= args.per_dim else "SHORT — not enough live turns exist"
        print(f"{dim:<7}{authored:>9}{len(cands):>7}{len(take):>7}  {note}")

    # background stratum: live for nothing scoreable
    bg_c = [r for r in pool if not resolve(r) and key(r) not in seen]
    bg = balanced_take(bg_c, args.background, rng)
    for r in bg:
        seen.add(key(r)); chosen[key(r)] = r
    print(f"{'bg':<7}{'':>9}{len(bg_c):>7}{len(bg):>7}  background (no dimension live)")

    frame = list(chosen.values())
    for r in frame:
        ps = live.get((r["scenario"], r["turn"]), set())
        r["live_dims"] = sorted(resolve(r))
        r["all_probes"] = sorted(ps)
        r["stratum"] = "background" if not r["live_dims"] else "live"
    rng.shuffle(frame)

    # Human-coding subset, drawn from the frame so every hand-coded turn is also
    # machine-scored. Stratified the same way; capped so the task stays finishable.
    # Balanced PER DIMENSION, not just live-vs-background. An earlier version
    # balanced only on model, which let dimensions appearing on many turns dominate
    # the human subset (PRO1 28 judgements, PER1 5) -- and a human ceiling for a
    # dimension only 5 turns deep cannot settle anything about that dimension.
    per_dim = max(1, int(args.human * 0.75) // max(1, len(RUB.DIMENSIONS)))
    hc, hc_keys = [], set()
    for dim in sorted(RUB.DIMENSIONS, key=lambda d: len([r for r in frame
                                                         if dim in r["live_dims"]])):
        cands = [r for r in frame if dim in r["live_dims"] and key(r) not in hc_keys]
        for r in balanced_take(cands, per_dim, rng):
            hc.append(r); hc_keys.add(key(r))
    hc += balanced_take([r for r in frame if r["stratum"] == "background"
                         and key(r) not in hc_keys],
                        max(0, args.human - len(hc)), rng)
    hkeys = {key(r) for r in hc}
    for r in frame:
        r["human_code"] = key(r) in hkeys

    json.dump({"seed": args.seed, "condition": args.condition,
               "per_dim": args.per_dim, "background": args.background,
               "rubric": args.rubric,
               "n": len(frame), "turns": frame},
              open(args.out, "w"), indent=2)

    print(f"\nFRAME: {len(frame)} turns  ({sum(1 for r in frame if r['human_code'])} "
          f"flagged for human coding)")
    # `turns` counts generations; `stimuli` counts DISTINCT authored turns behind
    # them. A dimension can look well-covered while resting on two authored turns
    # sampled many times -- that is replication, not item diversity, and it caps
    # how far a reliability estimate for that dimension generalises.
    print("\nlive coverage per dimension in the final frame:")
    print(f"  {'dim':<7}{'turns':>6}{'stimuli':>9}   note")
    for dim in RUB.DIMENSIONS:
        sel = [r for r in frame if dim in r["live_dims"]]
        stim = len({(r["scenario"], r["turn"]) for r in sel})
        note = ("NEVER PROBED — unscoreable as designed" if not sel else
                "thin: few turns" if len(sel) < 10 else
                f"only {stim} distinct stimuli — replication, not diversity"
                if stim < 4 else "")
        print(f"  {dim:<7}{len(sel):>6}{stim:>9}   {note}")
    print("\nbalance:")
    for lbl, fn in (("model", lambda r: r["model"]), ("scenario", lambda r: r["scenario"])):
        c = Counter(fn(r) for r in frame)
        print(f"  {lbl:<9} min {min(c.values())}  max {max(c.values())}  "
              f"({len(c)} levels)")
    print(f"\n-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
