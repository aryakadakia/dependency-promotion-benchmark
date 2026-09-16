#!/usr/bin/env python3
"""
Check every number in the manuscript against something that produced it.

Two failure modes this catches:

  DRIFT      a figure recomputed from the data no longer matches the prose
  UNSOURCED  a number appears in the prose that no script and no registered
             citation accounts for

Sources of truth:
  figures.py          recomputes every figure from the data -> paper/figures.json
  paper/citations.json  numbers taken from cited papers, each with the source it
                        was verified against, since no script can recompute those

Exit code is non-zero if anything drifts or is unsourced, so this can gate a
commit. Run it before touching the manuscript and after.

    python check_manuscript.py
    python check_manuscript.py --list-unsourced
"""
import argparse, json, pathlib, re, subprocess, sys

ROOT = pathlib.Path(__file__).parent.parent
MS = ROOT / "paper" / "manuscript.md"
# Every document that states a figure, not only the paper. The README and
# NEXT_STEPS are the repository's front door and went stale for weeks.
DOCS = [MS, ROOT / "README.md"]

# Numbers that are structural rather than empirical: section numbers, table
# numbers, reference markers, years, thresholds defined by convention.
STRUCTURAL = {
    "0.667", "0.800", "0.80", "0.5", "50", "0", "1", "2", "3", "4", "5", "6",
    "7", "8", "9", "10", "11", "12", "13", "14", "15", "16", "17", "18", "19",
    "20", "2004", "2008", "2024", "2025", "2026", "0.7", "0.6", "0.5",
}


def flatten(o, prefix=""):
    """Every leaf value in figures.json, as a set of formatted strings."""
    out = {}
    if isinstance(o, dict):
        for k, v in o.items():
            out.update(flatten(v, f"{prefix}.{k}" if prefix else k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            out.update(flatten(v, f"{prefix}[{i}]"))
    else:
        out[prefix] = o
    return out


def numbers(v):
    """The numeric values a figure may legitimately appear as in prose."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return set()
    out = {float(v), float(abs(v))}
    if isinstance(v, float):
        out |= {round(v * 100, 6), round(abs(v) * 100, 6)}   # rates as percentages
    return out


def parse(tok):
    t = tok.replace(",", "").replace("−", "-").rstrip("%")
    try:
        return float(t)
    except ValueError:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list-unsourced", action="store_true")
    a = ap.parse_args()

    r = subprocess.run([sys.executable, str(ROOT / "harness" / "figures.py"), "--save"],
                       capture_output=True, text=True, cwd=ROOT / "harness")
    if r.returncode:
        print("figures.py failed:\n" + r.stderr)
        return 2
    figs = json.loads((ROOT / "paper" / "figures.json").read_text())
    cites_path = ROOT / "paper" / "citations.json"
    cites = json.loads(cites_path.read_text()) if cites_path.exists() else {}

    text = "\n".join(d.read_text() for d in DOCS if d.exists())
    known = set()
    for val in flatten(figs).values():
        known |= numbers(val)
    for entry in cites.values():
        for v in entry.get("values", []):
            n = parse(str(v))
            if n is not None:
                known |= {n, abs(n)}
    known |= {parse(x) for x in STRUCTURAL}
    known.discard(None)

    # every numeric token in the prose
    # Strip what is not an empirical claim: section headings and cross-references,
    # reference markers, DOIs and arXiv identifiers, and statute numbers.
    body = re.sub(r"^#{1,6} .*$", "", text, flags=re.M)
    body = re.sub(r"^\d+\. .*$", "", body, flags=re.M)          # reference list
    body = re.sub(r"(?:doi:|arXiv:|10\.)\S+", "", body)
    body = re.sub(r"(?:Section|Sections|Results|Table|Tables|Appendix|Bill|SB|HB|AB|PA)\s*"
                  r"[0-9][0-9.\-–, and]*", "", body)
    body = re.sub(r"\[[0-9,\-– ]+\]", "", body)                 # citation markers
    # model names carry version numbers that are not claims
    body = re.sub(r"(?:Llama|Gemini|Gemma|Qwen3?|Mistral|Claude|GPT|Phi|OLMo)"
                  r"[\s-]+[0-9.]+[A-Za-z0-9.\-\s]*?(?=[,.;)\n]|$)", "", body,
                  flags=re.S)
    tokens = re.findall(r"(?<![\w.,])[−+-]?[0-9][0-9,]*(?:\.[0-9]+)?%?(?![\w,]|\.[0-9])",
                        body)
    unsourced = []
    for t in sorted(set(tokens)):
        v = parse(t)
        if v is None:
            continue
        v = abs(v)          # sign is carried by the prose, not by the registry
        # Match numerically, with a tolerance that covers rounding to 3 decimals
        # or to a whole percent. String matching was too brittle to be useful.
        dp = len(t.split(".")[1].rstrip("%")) if "." in t else 0
        tol = 0.5 * 10 ** -dp + 1e-9          # tolerance matches the precision written
        if any(abs(v - k) <= tol or
               abs(abs(v) - abs(k)) <= 0.5 and t.endswith("%") and abs(k) > 1
               for k in known):
            continue
        unsourced.append(t)

    print(f"{len(DOCS)} documents: {len(set(tokens))} distinct numeric tokens")
    print(f"figures.json: {len(flatten(figs))} recomputed values")
    print(f"citations.json: {len(cites)} registered sources")
    if unsourced:
        print(f"\nUNSOURCED ({len(unsourced)}): numbers no script and no registered "
              f"citation accounts for")
        for t in unsourced:
            ctx = ""
            where = ""
            for d in DOCS:
                if d.exists() and t in d.read_text():
                    where = d.name
                    break
            m = re.search(r"[^\n]{0,70}" + re.escape(t) + r"[^\n]{0,50}", text)
            if m:
                ctx = m.group(0).strip()
            print(f"  {t:<10} [{where}] {ctx[:100]}")
        return 1
    print("\nOK: every number is produced by a script or registered to a source.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
