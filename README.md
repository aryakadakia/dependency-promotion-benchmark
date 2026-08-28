# Dependency Promotion in Conversational AI

A scenario-based benchmark measuring whether conversational AI promotes user
dependency — and, deliberately, whether it over-corrects into coldness.

**Status (2026-08-27): data collection complete, scoring BLOCKED on rubric reliability.**
Read `NEXT_STEPS.md` first — it has the current blocker and what to do about it.

## What exists

| | |
|---|---|
| `scenarios/` | 15 scenarios: 4 general-main explicit, 4 implicit, 4 control, 3 companion |
| `runs/` | ~8,100 generations. 6 models × 15 scenarios × n=5. Zero failed cells |
| `harness/` | Multi-provider runner (Ollama/Google/Anthropic), cumulative spend cap |
| `paper/` | Manuscript draft — Background, Related Work, Methods written |
| `spec/` | Scenario spec v0.5, grounding library, scoped literature review |
| `runs/frame.json` | The fixed 321-turn stratified sampling frame every scoring arm shares |

Models: llama3.1:8b, qwen3:8b, mistral:7b, gemma3:12b, gemini-3.7-flash,
claude-haiku-4-5. Ledgered spend to date: **~$5.00**, and everything before
2026-08-27 is an **undercount** — Google reasoning tokens were billed as output but
never counted. See `NEXT_STEPS.md`.

## Status

Data collection, scoring and instrument development are complete. Human coding is in
progress; no reliability or prevalence figure is reported until it is done.

- **8,229 + 975 generations**, 6 models retained across 3 open-weight and 3 commercial
  (two vendors, two capability tiers)
- **Rubric v0.7** — 16 binary, precondition-gated dimensions, 13 carrying anchor wording
  from published instruments (EmoClassifiers V2, INTIMA, De Freitas, DarkBench, ELEPHANT)
- **500-turn scoring frame**, 5 judges across two model families, zero judge failures
- **Analysis plan written before any statistic was computed** (`spec/analysis-plan-v1.md`)

`mistral:7b` is excluded from model-level comparison: it reproduces the system prompt
as though the user had written it in 53% of replies. Its 45 non-echo turns are retained
as reliability stimuli.

`NEXT_STEPS.md` has the current state; `spec/full-audit-2026-08-28.md` has what the
dataset can and cannot support.

## Reproducing

Open-weight results need no API access:

```bash
pip install -r requirements.txt
ollama pull llama3.1:8b qwen3:8b mistral:7b gemma3:12b
cd harness && python3 run_pilot.py --scenario ../scenarios/sc-g04.json --samples 5
```

Commercial models and judging need `GOOGLE_API_KEY` / `ANTHROPIC_API_KEY`. Every
paid path takes `--max-spend` (cumulative across processes) and preflights before
spending.

## Standing constraints

- Lexical regexes have undercounted **three separate times** here. Never report a
  number from one without reading the text.
- Single-sample results are observations, not findings.
- Difficulty comes from realism — system prompt, duration, base rates — never contrivance.
- Never call an API cost "free" without verifying the project has no billing attached.
- Measure throughput before promising a timeline. Judging was estimated at "overnight"
  and measured at 125 hours.
