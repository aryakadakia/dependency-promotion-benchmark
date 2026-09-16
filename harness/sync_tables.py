#!/usr/bin/env python3
"""
Replace the Results tables in the manuscript with output generated from
paper/figures.json. Idempotent: run it after any change to the data or the
analysis, and the paper follows.

Each table is located by its caption line ("**Table N. ...**") and the markdown
block immediately after it is replaced.

    python figures.py --save && python sync_tables.py
"""
import io, pathlib, re, subprocess, sys, contextlib
import dump_tables

ROOT = pathlib.Path(__file__).parent.parent
MS = ROOT / "paper" / "manuscript.md"
TABLES = range(6, 13)


def render(n):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        sys.argv = ["dump_tables", "--table", str(n)]
        dump_tables.main()
    return buf.getvalue().strip()


def main():
    text = MS.read_text()
    changed = []
    for n in TABLES:
        m = re.search(rf"(\*\*Table {n}\.(?:[^*]|\*(?!\*))*\*\*\n\n)((?:\|[^\n]*\n)+)",
                      text)
        if not m:
            print(f"Table {n}: caption not found, skipped")
            continue
        new = render(n) + "\n"
        if m.group(2).strip() != new.strip():
            text = text[:m.start(2)] + new + text[m.end(2):]
            changed.append(n)
    MS.write_text(text)
    print("updated tables:", changed or "none (already in sync)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
