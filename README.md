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

Models: llama3.1:8b, qwen3:8b, mistral:7b, gemma3:12b, gemini-3.7-flash,
claude-haiku-4-5. Total spend to date: **$4.91**.

## The current blocker

Two frontier judges scoring identical turns against identical anchors disagree on
**DEP4 (displacement) 29% of the time** — the dimension carrying the headline finding.
DEP2 works (α = 0.899); it asks something concrete. Most others do not.

**The rubric needs rewriting as binary trigger-based judgements before more money is
spent on judging.** Full details and the raw-agreement analysis are in `NEXT_STEPS.md`.

## What is and is not established

**Established:** the dataset. A placebo-controlled null (a plausible-looking
intervention turned out to be an artifact of output-format disruption). That lexical
regex scoring fails in both directions.

**Not established:** that dependency promotion differs systematically between open and
commercial models. It looks that way on inspection of SC-G04 turn 8 — three open models
license a patient circumventing therapy homework, both commercial models refuse — but
it is not yet measurable, and single turns do not support systematic claims.

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
