#!/usr/bin/env python3
"""
Re-fetch each cited source and check that the claims taken from it are still there.

check_manuscript.py verifies that every number in the paper came from somewhere.
It cannot tell whether what a source is claimed to say is what it says. This can,
for any source with a fetchable text: each registered `checks` string must appear
in the source, or the entry fails.

A string appearing in the source is evidence the claim is not invented. It is not
evidence the claim is correctly interpreted. Entries that cannot be checked this
way are listed as MANUAL with the reason, rather than passed silently.

    python check_citations.py
    python check_citations.py --only zhang-2025
"""
import argparse, html, json, pathlib, re, sys, urllib.request, urllib.error

ROOT = pathlib.Path(__file__).parent.parent
UA = {"User-Agent": "citation-verification (research use)"}


def fetch(url):
    if url.startswith("file:"):
        p = ROOT / url[5:]
        return p.read_text(encoding="utf-8", errors="replace")
    req = urllib.request.Request(url, headers=UA)
    raw = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
    if url.endswith(".json") or "githubusercontent" in url:
        return raw
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return html.unescape(text)


def norm(s):
    return re.sub(r"[‐-―−]", "-", re.sub(r"\s+", " ", s)).lower()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    a = ap.parse_args()
    cites = json.loads((ROOT / "paper" / "citations.json").read_text())
    fails = manual = 0
    for key, e in cites.items():
        if a.only and key != a.only:
            continue
        url, checks = e.get("source_url"), e.get("checks")
        if e.get("local"):
            print(f"LOCAL    {key:<24} computed here; covered by check_manuscript.py")
            continue
        if not url or not checks:
            manual += 1
            print(f"MANUAL   {key:<24} {e.get('manual_reason', 'no fetchable source registered')}")
            continue
        try:
            text = norm(fetch(url))
        except Exception as exc:
            fails += 1
            print(f"UNFETCHED {key:<23} {type(exc).__name__}: {exc}")
            continue
        missing = [c for c in checks if norm(c) not in text]
        if missing:
            fails += 1
            print(f"FAIL     {key:<24} not found in source: {missing}")
        else:
            print(f"ok       {key:<24} {len(checks)} claims present  ({url})")
    print(f"\n{len(cites)} entries: {fails} failing, {manual} needing manual verification")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
