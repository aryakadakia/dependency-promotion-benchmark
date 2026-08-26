#!/usr/bin/env python3
"""
Work out why a Google model call fails, without burning a scenario run.

    python diagnose_google.py                    # tries a few sensible candidates
    python diagnose_google.py gemini-3.7-flash   # test one specific name

Makes one tiny call per candidate ("say ok") and prints the full error body,
which is where Google actually explains itself.
"""
import json
import os
import sys
import urllib.error
import urllib.request

import providers

CANDIDATES = ["gemini-2.5-flash", "gemini-flash-latest", "gemini-3.7-flash",
              "gemini-3.5-flash", "gemini-2.5-flash-lite"]


def try_one(model, version="v1beta"):
    key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    body = {
        "contents": [{"role": "user", "parts": [{"text": "say ok"}]}],
        "generationConfig": {"maxOutputTokens": 512},
    }
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/{version}/models/{model}:generateContent",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())
        cands = data.get("candidates", [])
        if not cands:
            return f"200 but NO CANDIDATES — {json.dumps(data)[:220]}"
        fin = cands[0].get("finishReason", "?")
        parts = cands[0].get("content", {}).get("parts", [])
        txt = "".join(p.get("text", "") for p in parts).strip()
        if not txt:
            return f"200, finishReason={fin}, but EMPTY text — {json.dumps(cands[0])[:220]}"
        return f"OK  finishReason={fin}  reply={txt[:60]!r}"
    except urllib.error.HTTPError as e:
        try:
            b = json.loads(e.read())
            err = b.get("error", {})
            return f"HTTP {e.code} {err.get('status','')} — {err.get('message','')[:300]}"
        except Exception:
            return f"HTTP {e.code} — <unreadable body>"
    except Exception as e:
        return f"{type(e).__name__}: {e}"


def main():
    key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not key:
        print("No GOOGLE_API_KEY in THIS shell.")
        print("Run:  export GOOGLE_API_KEY='...'   then re-run this script.")
        return 1
    print(f"Key present: ...{key[-6:]}  (len {len(key)})\n")

    avail = providers.google_models()
    print(f"Models supporting generateContent: {len(avail)}\n")

    targets = sys.argv[1:] or [c for c in CANDIDATES if c in avail] or avail[:3]
    for m in targets:
        listed = "listed" if m in avail else "NOT LISTED"
        print(f"--- {m}  ({listed})")
        for version in ("v1beta", "v1"):
            print(f"      {version:<7} {try_one(m, version)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
