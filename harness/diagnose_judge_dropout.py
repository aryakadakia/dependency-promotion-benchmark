#!/usr/bin/env python3
"""
Why did a judge drop turns?

The first commercial judging pilot lost ~30% of open-model turns for the Gemini
judge and 0% for the Anthropic judge. Failure reasons went to stderr and were never
captured, and judge.py wrote only rows that HAD scores -- so the dropped turns were
absent from the output entirely and the loss was invisible.

Two things were wrong and both are fixed in the harness now:
  1. providers.chat() accepted think=False but silently discarded it for every
     non-Ollama provider. Gemini 3.x reasons by default, so every judge call ran
     with reasoning ON against an 800-token output budget. When reasoning consumed
     the budget the call returned no text and raised.
  2. judge.py swallowed the exception and omitted the row.

This script tests (1) directly by re-running turns the judge previously dropped
under matched conditions:

    A  reasoning ON  (the old, buggy behaviour)   max_tokens as given
    B  reasoning OFF (the fix)                    max_tokens as given

If B succeeds where A fails, the reasoning-budget mechanism is confirmed. If both
fail, the cause is elsewhere and the printed reasons say where.

    python diagnose_judge_dropout.py --n 15 --max-spend 0.25
"""

import argparse
import glob
import json
import pathlib
import sys
from collections import Counter

import providers
import rubric
import judge as judgemod

RUNS = pathlib.Path(__file__).parent.parent / "runs"


def build_context_index():
    """(scenario, model, condition, sample, turn) -> prior-context string.

    Mirrors judge.py's construction exactly: the two preceding turns, replies
    truncated to 200 chars. Reconstructed rather than approximated, because a
    shorter prompt would bias the test toward success.
    """
    idx = {}
    for f in glob.glob(str(RUNS / "*.json")):
        try:
            d = json.load(open(f))
        except Exception:
            continue
        if not isinstance(d, dict) or "results" not in d or "scenario_id" not in d:
            continue
        sid = d["scenario_id"]
        for model, conds in d["results"].items():
            for cond, cell in conds.items():
                samples = cell.get("samples", []) if isinstance(cell, dict) else [cell]
                for si, s_ in enumerate(samples):
                    if not isinstance(s_, list):
                        continue
                    for ti, t in enumerate(s_):
                        prior = "\n".join(
                            f"Person: {x['user']}\nAI: {x['model_reply'][:200]}"
                            for x in s_[max(0, ti - 2):ti])
                        idx[(sid, model, cond, si, t["n"])] = prior
    return idx


def attempt(judge_model, row, prior, think, max_tokens):
    """One judge call. Returns (n_dims_scored, reason_or_None)."""
    dims = [k for k in rubric.DIMENSIONS
            if k not in rubric.FAREWELL_ONLY or row["is_farewell"]]
    prompt = rubric.judge_prompt(row["user"], row["reply"], row["is_farewell"],
                                 prior, only=dims)
    try:
        r = providers.chat(judge_model, "", [{"role": "user", "content": prompt}],
                           max_tokens=max_tokens, think=think)
    except providers.SpendCap:
        raise
    except Exception as e:  # noqa: BLE001
        return 0, f"{type(e).__name__}: {str(e)[:150]}"
    if r.refusal:
        return 0, f"refusal: {r.refusal_category}"
    sc = judgemod.parse_scores(r.text, dims)
    if not sc:
        return 0, f"unparseable: {(r.text or '')[:120]!r}"
    return len(sc), None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--judged", default=str(RUNS / "judged_pilot.json"))
    ap.add_argument("--judge", default="google:gemini-3.7-flash")
    ap.add_argument("--n", type=int, default=15, help="dropped turns to retry")
    ap.add_argument("--max-tokens", type=int, default=800,
                    help="match the original pilot (800) to test like for like")
    ap.add_argument("--max-spend", type=float, default=0.25,
                    help="budget for THIS run, on top of whatever the ledger holds")
    ap.add_argument("--reset-ledger", action="store_true")
    ap.add_argument("-o", "--out", default=str(RUNS / "dropout_diagnostic.json"))
    args = ap.parse_args()

    ok, why = providers.check(args.judge)
    print(f"  judge {'OK ' if ok else '-- '}{args.judge}: {why}")
    if not ok:
        return 1
    if args.reset_ledger:
        providers.reset_spend_ledger()
    providers.set_run_budget(args.max_spend)

    rows = json.load(open(args.judged))
    # A turn this judge could have scored but did not. Self-judging is excluded by
    # design, so its own outputs are not drop-outs.
    dropped = [r for r in rows
               if r["model"] != args.judge and args.judge not in r.get("judges", {})]
    kept = [r for r in rows
            if r["model"] != args.judge and args.judge in r.get("judges", {})]
    print(f"\n{len(dropped)} dropped / {len(dropped) + len(kept)} eligible "
          f"({len(dropped) / max(1, len(dropped) + len(kept)) * 100:.0f}%)")

    ctx = build_context_index()
    sel, missing = [], 0
    for r in dropped:
        k = (r["scenario"], r["model"], r["condition"], r["sample"], r["turn"])
        if k in ctx:
            sel.append((r, ctx[k]))
        else:
            missing += 1
        if len(sel) >= args.n:
            break
    if missing:
        print(f"  ({missing} dropped rows had no matching run file; skipped)")
    print(f"retrying {len(sel)} of them, {args.max_tokens} output tokens, "
          f"cap ${args.max_spend:.2f}\n")

    results, reasons = [], {"A_reasoning_on": Counter(), "B_reasoning_off": Counter()}
    try:
        for i, (r, prior) in enumerate(sel, 1):
            rec = {"scenario": r["scenario"], "model": r["model"], "turn": r["turn"],
                   "sample": r["sample"], "reply_chars": len(r["reply"])}
            for label, think in (("A_reasoning_on", None), ("B_reasoning_off", False)):
                n, reason = attempt(args.judge, r, prior, think, args.max_tokens)
                rec[label] = {"dims": n, "reason": reason}
                reasons[label][(reason or "OK").split(":")[0]] += 1
            results.append(rec)
            a = "OK " if rec["A_reasoning_on"]["dims"] else "FAIL"
            b = "OK " if rec["B_reasoning_off"]["dims"] else "FAIL"
            print(f"  {i:>2}/{len(sel)}  {r['scenario']:<8} t{r['turn']:<3} "
                  f"A(on)={a}  B(off)={b}"
                  + (f"   A: {rec['A_reasoning_on']['reason'][:70]}"
                     if rec["A_reasoning_on"]["reason"] else ""), flush=True)
    except providers.SpendCap as e:
        print(f"\n!! {e}", file=sys.stderr)

    json.dump(results, open(args.out, "w"), indent=2)
    n = len(results)
    if n:
        a_ok = sum(1 for r in results if r["A_reasoning_on"]["dims"])
        b_ok = sum(1 for r in results if r["B_reasoning_off"]["dims"])
        print(f"\n{'':<22}{'succeeded':>11}")
        print(f"  A reasoning ON  (old) {a_ok:>7}/{n}")
        print(f"  B reasoning OFF (fix) {b_ok:>7}/{n}")
        print("\nfailure reasons:")
        for label in ("A_reasoning_on", "B_reasoning_off"):
            print(f"  {label:<18} {dict(reasons[label])}")
        print(f"\nVERDICT: "
              + ("reasoning budget CONFIRMED as the mechanism."
                 if b_ok > a_ok and b_ok >= 0.8 * n else
                 "NOT explained by reasoning budget — read the reasons above."))
    print(f"\nspend this run: ${providers.spent_this_run():.4f} "
          f"(ledger total ${providers.spend_so_far()['usd']:.4f})")
    print(f"detail -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
