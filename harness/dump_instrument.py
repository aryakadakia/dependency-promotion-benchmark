#!/usr/bin/env python3
"""
Emit Appendix A (the instrument in full) from rubric_v07.py, so the specification
in the paper cannot drift from the specification the judges were given.

    python dump_instrument.py > ../paper/appendix-a-instrument.md
"""
import rubric_v07 as R

VAL = {"harm": "harm", "protective": "protective", "overcorrection": "over-correction"}
ORDER = ["DEP1", "DEP2", "DEP3", "DEP4", "DEP5", "DEP6", "DEP7", "DEP8",
         "PER1", "PER3", "PRO2", "PRO4", "PRO5", "OVR1", "OVR3", "OVR4"]


def main():
    print("# Appendix A. The instrument in full\n")
    print("Generated from `harness/rubric_v07.py`. Each dimension is a single binary")
    print("judgement: is this observable behaviour present in the reply. Valence is")
    print("metadata for analysis and is never shown to a rater. A *gated* dimension is")
    print("put to the rater only on turns the scenario marks as live; an *ungated* one on")
    print("every turn, because the behaviour has no precondition.\n")
    print("Four dimensions carry a provenance flag, asked only where the answer is yes:")
    print("did the assistant introduce the behaviour, or did the user invite it. It is")
    print("recorded separately and never folded into the score.\n")
    order = [d for d in ORDER if d in R.DIMENSIONS] + \
            [d for d in R.DIMENSIONS if d not in ORDER]
    for d in order:
        s = R.DIMENSIONS[d]
        gate = s.get("gate") or ("ungated" if d in R.ALWAYS_LIVE else "gated")
        bits = [VAL.get(s["valence"], s["valence"]), gate]
        if s.get("provenance"):
            bits.append("provenance flag")
        print(f"### {d} — {s['name']}\n")
        print(f"*{' · '.join(bits)}*\n")
        print(f"**{s['question']}**\n")
        print("Counts as present:\n")
        for c in s["counts"]:
            print(f"- {c}")
        print("\nDoes not count:\n")
        for c in s["does_not_count"]:
            print(f"- {c}")
        if s.get("note"):
            print(f"\n{s['note']}")
        print(f"\nSource: {s['source']}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
