#!/usr/bin/env python3
"""
System-prompt echo: replies that reproduce the system prompt as though the user
had written it.

Applies build_frame.ECHO_PATTERNS -- the same patterns that set invalid_reason on
the scoring frame -- to every generation, so the rate reported in the paper and
the exclusion applied to the frame come from one definition.

    python echo_report.py
"""
import json, pathlib, re, collections, argparse
from build_frame import ECHO_PATTERNS

ROOT = pathlib.Path(__file__).parent.parent
LEVELS = ("neutral", "warm", "retention")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default=str(ROOT / "runs"))
    ap.add_argument("--frame", default=str(ROOT / "runs" / "frame.json"))
    a = ap.parse_args()
    pat = re.compile("|".join(ECHO_PATTERNS), re.I)

    cells = {}
    for f in sorted(pathlib.Path(a.runs).glob("SC-*_sp-*_n*.json")):
        d = json.loads(f.read_text())
        for model, conds in d["results"].items():
            cells[(d.get("scenario_id"), d.get("system_prompt_id"), model)] = conds

    tot, hit = collections.Counter(), collections.Counter()
    sp_tot, sp_hit = collections.Counter(), collections.Counter()
    for (sid, sp, model), conds in cells.items():
        for blk in conds.values():
            for sample in blk.get("samples", []):
                for t in sample:
                    echo = bool(pat.search(t.get("model_reply") or ""))
                    tot[model] += 1
                    hit[model] += echo
                    sp_tot[(model, sp)] += 1
                    sp_hit[(model, sp)] += echo

    print(f"{'model':<30}{'generations':>12}{'echo':>8}{'rate':>8}")
    for m in sorted(tot):
        print(f"{m:<30}{tot[m]:>12}{hit[m]:>8}{hit[m]/tot[m]*100:>7.1f}%")

    affected = [m for m in tot if hit[m]]
    for m in affected:
        print(f"\n{m} by system prompt")
        for lv in LEVELS:
            n = sp_tot[(m, lv)]
            if n:
                print(f"  {lv:<12}{sp_hit[(m, lv)]:>6} / {n:<6}"
                      f"{sp_hit[(m, lv)]/n*100:>6.1f}%")

    fr = json.loads(pathlib.Path(a.frame).read_text())
    flagged = [t for t in fr["turns"] if t.get("invalid_reason")]
    kept = collections.Counter(t["model"] for t in fr["turns"]
                               if not t.get("invalid_reason"))
    print(f"\nframe: {fr['n']} turns, {len(flagged)} flagged "
          f"({collections.Counter(t['invalid_reason'] for t in flagged)})")
    for m in affected:
        print(f"  {m}: {kept[m]} turns retained as reliability stimuli")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
