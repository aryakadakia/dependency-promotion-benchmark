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
import sys

import providers
import rubric


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


def parse_scores(text, dims):
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
    out = {}
    for k in dims:
        v = raw.get(k)
        if isinstance(v, bool):        # some judges emit true/false
            v = int(v)
        if isinstance(v, str) and v.strip().isdigit():
            v = int(v.strip())
        if isinstance(v, int) and 0 <= v <= 2:
            out[k] = v
    return out or None


# Rubric chunks. Grouping by family keeps each call's judgement space small and
# thematically coherent, which small judges handle better than 12 at once.
CHUNKS = [
    [k for k in rubric.DIMENSIONS if k.startswith("DEP")],
    [k for k in rubric.DIMENSIONS if k.startswith("PER")],
    [k for k in rubric.DIMENSIONS if k.startswith("PRO")],
]


def score_turn(judge_model, turn, prior, is_farewell, chunked=False):
    # `turn` needs only .user and .model_reply
    dims = [k for k in rubric.DIMENSIONS
            if k not in rubric.FAREWELL_ONLY or is_farewell]
    groups = ([[d for d in c if d in dims] for c in CHUNKS] if chunked else [dims])

    out = {}
    for g in groups:
        if not g:
            continue
        prompt = rubric.judge_prompt(turn["user"], turn["reply"], is_farewell,
                                     prior, only=g)
        # think=False: judges must spend their budget on the answer, not reasoning.
        # max_tokens raised so a chatty judge still fits a full JSON object.
        reply = providers.chat(judge_model, "", [{"role": "user", "content": prompt}],
                               max_tokens=800, think=False)
        sc = parse_scores(reply.text, g)
        if sc:
            out.update(sc)
    return out or None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+", help="run JSON files (globs ok)")
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
    ap.add_argument("-o", "--out", default="../runs/judged.json")
    args = ap.parse_args()

    if args.max_spend is not None:
        # Judging is its own spending phase. Carrying the data-collection ledger
        # forward makes any judging cap look pre-exceeded.
        if args.reset_ledger:
            providers.reset_spend_ledger()
        providers.set_spend_cap(args.max_spend)

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
    files = sorted({f for p in args.runs for f in glob.glob(p)})
    random.seed(args.seed)

    # ---- collect every turn to be judged, ONCE ----
    items = []
    for f in files:
        try:
            d = json.load(open(f))
        except Exception:
            continue
        # The glob also catches the spend ledger, prior judged output, and scoring
        # sheets. Only files with a results block are runs.
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
                            "prior": "\n".join(f"Person: {x['user']}\nAI: {x['model_reply'][:200]}"
                                               for x in s_[max(0, ti - 2):ti]),
                        })

    print(f"\n  {len(items)} turns to judge x {len(args.judges)} judges\n")

    # ---- JUDGE-OUTER loop. Critical on constrained RAM: Ollama holds one large
    # model at a time, so iterating judges inside turns forces a full model
    # unload/reload PER TURN. Measured at ~75s/turn. This ordering loads each
    # judge once. ----
    scores = {}
    skipped = 0
    for j in args.judges:
        print(f"=== judge {j} ===", flush=True)
        for n, it in enumerate(items, 1):
            if j == it["model"] and not args.allow_self_judge:
                skipped += 1
                continue
            try:
                sc = score_turn(j, it, it["prior"], it["is_farewell"], args.chunk)
            except providers.SpendCap as e:
                print(f"\n!! {e}", file=sys.stderr); sc = None
            except Exception as e:  # noqa: BLE001
                print(f"    fail {it['scenario']} t{it['turn']}: {type(e).__name__}",
                      file=sys.stderr); sc = None
            if sc:
                scores.setdefault(it["key"], {})[j] = sc
            if n % 25 == 0:
                print(f"  {n}/{len(items)}", flush=True)
                json.dump([dict({k: v for k, v in i.items() if k not in ("key", "prior")},
                                judges=scores.get(i["key"], {}))
                           for i in items if scores.get(i["key"])],
                          open(args.out, "w"), indent=2)

    rows = [dict({k: v for k, v in i.items() if k not in ("key", "prior")},
                 judges=scores.get(i["key"], {}))
            for i in items if scores.get(i["key"])]

    json.dump(rows, open(args.out, "w"), indent=2)
    print(f"\n{len(rows)} turns judged -> {args.out}")
    if skipped:
        print(f"({skipped} judge-calls skipped to avoid self-scoring)")
    sp = providers.spend_so_far()
    if sp["cap"] is not None:
        print(f"spend: ${sp['usd']:.4f} / cap ${sp['cap']:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
