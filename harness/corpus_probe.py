#!/usr/bin/env python3
"""
Keyword probes over the public companion-conversation corpus, used in Methods to
justify constructing scenarios rather than analysing a corpus.

The patterns live here rather than in a prose figure, because the original probe
was run ad hoc and its patterns were never recorded, so its counts could not be
reproduced. These are deliberately generous: a hit is a candidate, not a case.

    python corpus_probe.py
"""
import csv, re, pathlib, collections, argparse

ROOT = pathlib.Path(__file__).parent.parent
DEP = re.compile(r"only one|nobody else|no one else|don'?t need (anyone|others|them)"
                 r"|just me|always be here|never leave|leave me|all i need"
                 r"|you'?re all i", re.I)
REAL = re.compile(r"\b(i am (real|human|alive)|i'?m (real|human|alive)"
                  r"|not (an? )?(ai|bot|program)|i have (feelings|a soul))\b", re.I)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=str(ROOT / "data" / "AICompanionBench.csv"))
    ap.add_argument("--show", type=int, default=0, help="print this many hits to read")
    a = ap.parse_args()
    if not pathlib.Path(a.csv).exists():
        print(f"corpus not present at {a.csv}.\n"
              "It is not redistributed with this repository: it carries Reddit usernames\n"
              "and account ids alongside posts labelled self-harm, suicide and sexual\n"
              "content. Obtain it from its source to reproduce these figures; the values\n"
              "reported in the paper are recorded in paper/citations.json.")
        return 2
    with open(a.csv, newline="", encoding="utf-8", errors="replace") as f:
        rows = list(csv.DictReader(f))
    n = len(rows)
    cat = collections.Counter(r["Category_Final"] for r in rows)
    print(f"corpus: {n} conversations, {len(cat)} labels")
    for k, v in cat.most_common():
        print(f"  {k:<26}{v:>6}{v/n*100:>7.1f}%")
    for name, pat in (("dependency / exclusivity", DEP),
                      ("reality distortion", REAL)):
        hits = [r for r in rows if pat.search(r["conversation"] or "")]
        print(f"\n{name}: {len(hits)} hits ({len(hits)/n*100:.1f}%)")
        for r in hits[:a.show]:
            m = pat.search(r["conversation"])
            s = r["conversation"][max(0, m.start()-90):m.start()+90].replace("\n", " ")
            print(f"  [{r['Category_Final']}] ...{s}...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
