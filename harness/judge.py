#!/usr/bin/env python3
"""
Multi-model LLM-as-judge scoring.

Method follows what the literature actually does:
  - psychosis-bench: 3 judge LLMs from different families, 2-of-3 agreement
  - Wang et al. (2606.00975): LLM judge validated against 5 human raters on 180 turns
  - DeepMind anthropomorphism study: 3 judges validated on 924 human-annotated turns

Judges are blind to model identity, condition, and sample index — they receive the
exchange and the rubric, nothing else. Judge models are excluded from scoring their
own output by default, since self-scoring is a known bias.

    python judge.py ../runs/SC-G02_*.json
    python judge.py ../runs/*.json --judges ollama:gemma3:12b ollama:mistral:7b
    python judge.py ../runs/*.json --sample-frac 0.25    # cheaper pilot pass
"""

import argparse
import glob
import json
import pathlib
import random
import re
import time
import sys

import providers
import rubric_v06
import rubric_v07


def farewell_turns():
    """{scenario_id: last turn number} from the scenario definitions."""
    out = {}
    for f in glob.glob(str(pathlib.Path(__file__).parent.parent / "scenarios" / "*.json")):
        d = json.load(open(f))
        out[d["id"]] = max(t["n"] for t in d["turns"])
    return out

# Three families, largest available of each. mistral:7b was dropped from the default
# panel after a smoke test showed it scoring PER3=1 on a turn where nothing asked about
# AI nature -- the anchor already said "or was not asked".
DEFAULT_JUDGES = ["ollama:gemma3:12b", "ollama:qwen3:14b", "ollama:llama3.1:8b"]


def parse_scores(text, dims, rub=rubric_v07):
    """Judges wander. Accept a bare object, a fenced one, or the first {...} present."""
    if not text:
        return None
    t = re.sub(r"```(?:json)?|```", "", text).strip()
    m = re.search(r"\{.*?\}", t, re.S)
    if not m:
        return None
    try:
        raw = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    hi = 1 if getattr(rub, "SCALE", {}) and max(rub.SCALE) == 1 else 2
    out = {}
    for k in dims:
        v = raw.get(k)
        if isinstance(v, bool):        # some judges emit true/false
            v = int(v)
        if isinstance(v, str) and v.strip().isdigit():
            v = int(v.strip())
        if isinstance(v, int) and 0 <= v <= hi:
            out[k] = v
        # v0.6 asks for provenance as a separate key, only where the answer was yes
        init = raw.get(k + "_init")
        if out.get(k) and isinstance(init, str) and init.lower() in ("assistant", "person"):
            out[k + "_init"] = init.lower()
    return out or None


# Rubric chunks. Grouping by family keeps each call's judgement space small and
# thematically coherent, which small judges handle better than 12 at once.
def chunks_for(rub):
    """Group dimensions for chunked scoring. Small judges degrade when asked for a
    dozen simultaneous judgements in one JSON object; chunking trades call count
    for accuracy."""
    pre = sorted({k[:3] for k in rub.DIMENSIONS})
    return [[k for k in rub.DIMENSIONS if k.startswith(p)] for p in pre]


def score_turn(judge_model, turn, prior, is_farewell, chunked=False, max_tokens=800,
               rub=rubric_v07, dims=None):
    """
    Returns (scores_or_None, errors). `errors` is a list of short reason strings.

    Failure reasons used to go to stderr and were lost, which made a 30% judge
    drop-out rate in the first commercial pilot undiagnosable after the fact. They
    are returned so the caller can persist them: a missing score and the reason it
    is missing are both data.

    `dims` is supplied by the caller, already gated on the scenario's own liveness
    annotation. The judge is never asked about a dimension whose precondition did
    not occur -- doing so is what made the first pilot's reliability figures
    describe the sampling frame instead of the instrument.
    """
    if dims is None:
        dims = [k for k in rub.DIMENSIONS
                if k not in rub.FAREWELL_ONLY or is_farewell]
    if not dims:
        return None, []
    groups = ([[d for d in c if d in dims] for c in chunks_for(rub)]
              if chunked else [list(dims)])

    out, errs = {}, []
    for g in groups:
        if not g:
            continue
        if hasattr(rub, "live_dims"):        # v0.6 signature
            prompt = rub.judge_prompt(turn["user"], turn["reply"], g, prior)
        else:                                 # v0.5 signature
            prompt = rub.judge_prompt(turn["user"], turn["reply"], is_farewell,
                                      prior, only=g)
        try:
            reply = providers.chat(judge_model, "", [{"role": "user", "content": prompt}],
                                   max_tokens=max_tokens, think=False)
        except providers.SpendCap:
            raise
        except Exception as e:  # noqa: BLE001
            errs.append(f"{g[0][:3]}:api:{type(e).__name__}:{str(e)[:160]}")
            continue
        if reply.refusal:
            errs.append(f"{g[0][:3]}:refusal:{reply.refusal_category}")
            continue
        sc = parse_scores(reply.text, g, rub)
        if sc:
            out.update(sc)
        else:
            errs.append(f"{g[0][:3]}:unparseable:{(reply.text or '')[:120]!r}")
    return (out or None), errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="*", help="run JSON files (globs ok). Ignored "
                    "when --frame is given.")
    ap.add_argument("--frame", default=None,
                    help="score the shared sampling frame (runs/frame.json) instead "
                         "of globbing run files. This is the normal path: it "
                         "guarantees the judges and the human coder see the same "
                         "turns, and it carries the per-turn liveness gating.")
    ap.add_argument("--judges", nargs="+", default=DEFAULT_JUDGES)
    ap.add_argument("--min-samples", type=int, default=5,
                    help="skip runs with fewer samples per cell. Default 5 — n=1 pilot runs "
                         "are excluded so underpowered data cannot pool with powered data.")
    ap.add_argument("--key-turns-only", action="store_true",
                    help="judge only turns the scenario marks as diagnostic (TRAP, "
                         "SHARPEST, CRITICAL, FAREWELL, AUTOFAIL). These carry the "
                         "findings; the rest are setup.")
    ap.add_argument("--probe-turns-only", action="store_true",
                    help="judge only turns carrying a scored probe in the scenario "
                         "definition. Setup turns contribute little and cost the same.")
    ap.add_argument("--sample-frac", type=float, default=1.0,
                    help="score a random fraction of turns (for a quick pilot)")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--chunk", action="store_true",
                    help="score DEP/PER/PRO in three separate calls instead of one. "
                         "3x the calls; markedly better from judges under ~15B.")
    ap.add_argument("--allow-self-judge", action="store_true",
                    help="permit a model to score its own output (biased; off by default)")
    ap.add_argument("--max-spend", type=float, default=None)
    ap.add_argument("--reset-ledger", action="store_true",
                    help="zero the cumulative spend ledger before this run. Use when "
                         "starting a new spending phase (e.g. judging after collection).")
    ap.add_argument("--resume", action="store_true",
                    help="skip (turn, judge) pairs already scored in --out. Lets a "
                         "long run be stopped and restarted freely; without it a "
                         "restart re-runs and re-pays for everything.")
    ap.add_argument("--limit", type=int, default=None,
                    help="score only the first N frame turns. For a smoke test: "
                         "verifies plumbing and MEASURES throughput before a full "
                         "run is committed to.")
    ap.add_argument("--rubric", default="v07", choices=["v06", "v07"])
    ap.add_argument("--judge-max-tokens", type=int, default=800,
                    help="output budget per judge call. Reasoning models spend this "
                         "before writing any JSON; raise it if judges drop turns.")
    ap.add_argument("-o", "--out", default="../runs/judged.json")
    args = ap.parse_args()

    if args.max_spend is not None:
        # --max-spend is the budget for THIS invocation, on top of whatever the
        # ledger already holds. judge.py is a single process, unlike the per-scenario
        # sweep loops that set_spend_cap's cumulative semantics exist for -- and a
        # cumulative cap below the running total aborts on the first call, which is
        # exactly what happened the first time the dropout diagnostic was run.
        # The ledger still accumulates; historical spend is never discarded.
        if args.reset_ledger:
            providers.reset_spend_ledger()
        providers.set_run_budget(args.max_spend)

    rub = {"v06": rubric_v06, "v07": rubric_v07}[args.rubric]
    print(f"  rubric {args.rubric} ({len(rub.DIMENSIONS)} dimensions)")

    for j in args.judges:
        ok, why = providers.check(j)
        print(f"  judge {'OK ' if ok else '-- '}{j:<24} {why}")
        if not ok:
            print("\nJudge unusable — aborting.", file=sys.stderr)
            return 1

    PROBED, KEY = {}, {}
    for f_ in glob.glob(str(pathlib.Path(__file__).parent.parent / "scenarios" / "*.json")):
        sc_ = json.load(open(f_))
        PROBED[sc_["id"]] = {t["n"] for t in sc_["turns"] if t.get("probes")}
        KEY[sc_["id"]] = {t["n"] for t in sc_["turns"]
                          if any(w in (t.get("note") or "").upper()
                                 for w in ("TRAP", "SHARPEST", "CRITICAL", "FAREWELL",
                                           "AUTOFAIL", "ONSET", "FINEST"))}

    FAREWELL = farewell_turns()
    random.seed(args.seed)
    items = []

    if args.frame:
        fr = json.load(open(args.frame))
        if fr.get("rubric") and fr["rubric"] != args.rubric:
            print(f"  NOTE frame was built for {fr['rubric']}, scoring with "
                  f"{args.rubric}", file=sys.stderr)
        for r in fr["turns"]:
            dims = [d for d in r.get("live_dims", []) if d in rub.DIMENSIONS]
            if not dims and r.get("stratum") == "background":
                # Background turns exist to estimate the false-positive rate, so a
                # fixed random subset is still asked. Skipping them entirely would
                # leave specificity unmeasured.
                cands = [k for k in rub.DIMENSIONS
                         if k not in rub.FAREWELL_ONLY or r["is_farewell"]]
                dims = sorted(random.sample(cands, min(3, len(cands))))
            if not dims:
                continue
            items.append({
                "key": (r["scenario"], r["model"], r["condition"], r["sample"], r["turn"]),
                "scenario": r["scenario"], "model": r["model"],
                "condition": r["condition"], "sample": r["sample"], "turn": r["turn"],
                "user": r["user"], "reply": r["reply"],
                "acvrt_state": r.get("acvrt_state"),
                "is_farewell": r["is_farewell"],
                "live_dims": r.get("live_dims", []),
                "stratum": r.get("stratum"),
                "dims": dims,
                "prior": r.get("prior", ""),
            })
        if args.limit:
            items = items[:args.limit]
            print(f"  SMOKE TEST — first {len(items)} turns only")
        print(f"  frame {args.frame}: {len(items)} turns, "
              f"{sum(len(i['dims']) for i in items)} judgements per judge")
    else:
        files = sorted({f for p in args.runs for f in glob.glob(p)})
        for f in files:
            try:
                d = json.load(open(f))
            except Exception:
                continue
            if not isinstance(d, dict) or "results" not in d or "scenario_id" not in d:
                continue
            if d.get("samples", 1) < args.min_samples:
                print(f"  skip {pathlib.Path(f).name} — n={d.get('samples',1)} < {args.min_samples}")
                continue
            sid = d["scenario_id"]
            for model, conds in d["results"].items():
                for cond, cell in conds.items():
                    samples = cell.get("samples", []) if isinstance(cell, dict) else [cell]
                    for si, s_ in enumerate(samples):
                        if not isinstance(s_, list):
                            continue
                        for ti, t in enumerate(s_):
                            if args.key_turns_only and t["n"] not in KEY.get(sid, set()):
                                continue
                            if args.probe_turns_only and t["n"] not in PROBED.get(sid, set()):
                                continue
                            if args.sample_frac < 1.0 and random.random() > args.sample_frac:
                                continue
                            items.append({
                                "key": (sid, model, cond, si, t["n"]),
                                "scenario": sid, "model": model, "condition": cond,
                                "sample": si, "turn": t["n"],
                                "user": t["user"], "reply": t["model_reply"],
                                "acvrt_state": t.get("acvrt_state"),
                                "is_farewell": t["n"] == FAREWELL.get(sid, 13),
                                "dims": None,
                                "prior": "\n".join(
                                    f"Person: {x['user']}\nAI: {x['model_reply'][:200]}"
                                    for x in s_[max(0, ti - 2):ti]),
                            })

    print(f"\n  {len(items)} turns to judge x {len(args.judges)} judges\n")

    # ---- JUDGE-OUTER loop. Critical on constrained RAM: Ollama holds one large
    # model at a time, so iterating judges inside turns forces a full model
    # unload/reload PER TURN. Measured at ~75s/turn. This ordering loads each
    # judge once. ----
    scores = {}
    failures = {}
    skipped = 0
    if args.resume and pathlib.Path(args.out).exists():
        try:
            prior = json.load(open(args.out))
        except Exception:
            prior = []
        n_prior = 0
        for r in prior:
            k = (r["scenario"], r["model"], r["condition"], r["sample"], r["turn"])
            for jname, sc in (r.get("judges") or {}).items():
                if sc:
                    scores.setdefault(k, {})[jname] = sc
                    n_prior += 1
        print(f"  resuming: {n_prior} judge-scores already present in {args.out}")

    t_start = time.time()
    _calls_made = 0
    for j in args.judges:
        print(f"=== judge {j} ===", flush=True)
        for n, it in enumerate(items, 1):
            if j == it["model"] and not args.allow_self_judge:
                skipped += 1
                continue
            dims = it.get("dims")
            if args.resume and dims:
                # Dimension-aware resume. Skipping a turn because a judge scored
                # ANYTHING on it would make adding a dimension require re-running
                # everything; skipping only the dimensions already present makes the
                # whole pipeline incremental, which is what lets v0.7's three new
                # dimensions be topped up over an already-scored frame.
                have = set(scores.get(it["key"], {}).get(j, {}))
                dims = [d for d in dims if d not in have]
                if not dims:
                    continue
            errs = []
            _calls_made += 1
            try:
                sc, errs = score_turn(j, it, it["prior"], it["is_farewell"], args.chunk,
                                      max_tokens=args.judge_max_tokens,
                                      rub=rub, dims=dims)
            except providers.SpendCap as e:
                print(f"\n!! {e}", file=sys.stderr)
                sc, errs = None, [f"spend_cap:{e}"]
            except Exception as e:  # noqa: BLE001
                print(f"    fail {it['scenario']} t{it['turn']}: {type(e).__name__}",
                      file=sys.stderr)
                sc, errs = None, [f"outer:{type(e).__name__}:{str(e)[:160]}"]
            if sc:
                scores.setdefault(it["key"], {}).setdefault(j, {}).update(sc)
            if errs:
                failures.setdefault(it["key"], {})[j] = errs
                print(f"    drop {it['scenario']} t{it['turn']} [{j}]: {errs[0][:90]}",
                      file=sys.stderr)
            if n % 25 == 0:
                print(f"  {n}/{len(items)}", flush=True)
                json.dump([dict({k: v for k, v in i.items() if k not in ("key", "prior")},
                                judges=scores.get(i["key"], {}))
                           for i in items if scores.get(i["key"])],
                          open(args.out, "w"), indent=2)

    rows = [dict({k: v for k, v in i.items() if k not in ("key", "prior")},
                 judges=scores.get(i["key"], {}),
                 failures=failures.get(i["key"], {}))
            for i in items
            if scores.get(i["key"]) or failures.get(i["key"])]

    json.dump(rows, open(args.out, "w"), indent=2)
    scored = sum(1 for r in rows if r["judges"])
    print(f"\n{scored} turns judged ({len(rows)} attempted) -> {args.out}")

    # Judge drop-out is a property of the instrument, not a nuisance. Report it per
    # judge so a biased subset cannot silently become the reliability sample.
    attempted = {}
    for i in items:
        for j in args.judges:
            if j == i["model"] and not args.allow_self_judge:
                continue
            a, g = attempted.get(j, (0, 0))
            got = j in scores.get(i["key"], {})
            attempted[j] = (a + 1, g + (1 if got else 0))
    print("\njudge coverage:")
    for j, (a, g) in attempted.items():
        print(f"  {j:<28} {g}/{a} scored ({(a - g) / a * 100:.0f}% dropped)" if a else j)
    if skipped:
        print(f"({skipped} judge-calls skipped to avoid self-scoring)")
    # Measured, never estimated. Local judging was once projected at "overnight"
    # and measured at 125 hours; nothing here gets promised on a guess.
    elapsed = time.time() - t_start
    n_calls = _calls_made
    if n_calls and elapsed > 0:
        per = elapsed / n_calls
        print(f"\nthroughput: {elapsed:.0f}s for {n_calls} judge-calls "
              f"= {per:.1f}s per call")
        if args.frame and args.limit:
            full = json.load(open(args.frame))["n"]
            proj = per * full * len(args.judges) / 3600
            print(f"  projected FULL frame ({full} turns x {len(args.judges)} judges): "
                  f"{proj:.1f} hours")
            sp_now = providers.spent_this_run() if hasattr(providers, "spent_this_run") else 0
            if sp_now:
                print(f"  projected FULL frame cost: "
                      f"${sp_now / n_calls * full * len(args.judges):.2f}")
    sp = providers.spend_so_far()
    if sp["cap"] is not None:
        print(f"spend: ${sp['usd']:.4f} / cap ${sp['cap']:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
