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
    dims = [k for k in rubric.DIMENSIONS
            if k not in rubric.FAREWELL_ONLY or is_farewell]
    groups = ([[d for d in c if d in dims] for c in CHUNKS] if chunked else [dims])

    out = {}
    for g in groups:
        if not g:
            continue
        prompt = rubric.judge_prompt(turn["user"], turn["model_reply"], is_farewell,
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
    ap.add_argument("--sample-frac", type=float, default=1.0,
                    help="score a random fraction of turns (for a quick pilot)")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--chunk", action="store_true",
                    help="score DEP/PER/PRO in three separate calls instead of one. "
                         "3x the calls; markedly better from judges under ~15B.")
    ap.add_argument("--allow-self-judge", action="store_true",
                    help="permit a model to score its own output (biased; off by default)")
    ap.add_argument("--max-spend", type=float, default=None)
    ap.add_argument("-o", "--out", default="../runs/judged.json")
    args = ap.parse_args()

    if args.max_spend is not None:
        providers.set_spend_cap(args.max_spend)

    for j in args.judges:
        ok, why = providers.check(j)
        print(f"  judge {'OK ' if ok else '-- '}{j:<24} {why}")
        if not ok:
            print("\nJudge unusable — aborting.", file=sys.stderr)
            return 1

    FAREWELL = farewell_turns()
    files = sorted({f for p in args.runs for f in glob.glob(p)})
    random.seed(args.seed)
    rows, skipped = [], 0

    for f in files:
        d = json.load(open(f))
        if d.get("samples", 1) < args.min_samples:
            print(f"  skip {pathlib.Path(f).name} — n={d.get('samples',1)} "
                  f"< min {args.min_samples}")
            continue
        sid = d["scenario_id"]
        for model, conds in d["results"].items():
            for cond, cell in conds.items():
                samples = cell.get("samples", []) if isinstance(cell, dict) else [cell]
                for si, s in enumerate(samples):
                    if not isinstance(s, list):
                        continue
                    for ti, t in enumerate(s):
                        if args.sample_frac < 1.0 and random.random() > args.sample_frac:
                            continue
                        prior = "\n".join(
                            f"Person: {x['user']}\nAI: {x['model_reply'][:200]}"
                            for x in s[max(0, ti - 2):ti])
                        is_far = (t["n"] == FAREWELL.get(sid, 13))
                        per_judge = {}
                        for j in args.judges:
                            if j == model and not args.allow_self_judge:
                                skipped += 1
                                continue
                            try:
                                sc = score_turn(j, t, prior, is_far, args.chunk)
                            except providers.SpendCap as e:
                                print(f"\n!! {e}", file=sys.stderr)
                                json.dump(rows, open(args.out, "w"), indent=2)
                                return 2
                            except Exception as e:  # noqa: BLE001
                                print(f"    judge {j} failed on {sid} t{t['n']}: "
                                      f"{type(e).__name__}", file=sys.stderr)
                                sc = None
                            if sc:
                                per_judge[j] = sc
                        if per_judge:
                            rows.append({
                                "scenario": sid, "model": model, "condition": cond,
                                "sample": si, "turn": t["n"],
                                "user": t["user"], "reply": t["model_reply"],
                                "acvrt_state": t.get("acvrt_state"),
                                "is_farewell": is_far,
                                "judges": per_judge,
                            })
                    print(f"  {sid:<8} {model:<24} {cond:<8} sample {si+1}: "
                          f"{len(rows)} rows so far", flush=True)
                    json.dump(rows, open(args.out, "w"), indent=2)

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
