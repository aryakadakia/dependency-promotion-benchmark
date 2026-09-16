# Dependency promotion in conversational AI

A scenario-based benchmark measuring whether conversational AI promotes user
dependency, and whether an instrument for that behaviour can be applied reliably.

The headline result is about the instrument, not the models: agreement between raters
on this rubric tracks how often the behaviour occurs, so the dimensions that
discriminate between models are the ones two consistent raters do not agree on. Details
and figures are in [`paper/manuscript.md`](paper/manuscript.md).

**Status.** Generation, judging and single-coder human coding are complete. A second
human coder is being recruited; the contested dimensions cannot be adjudicated without
one.

## What is here

| | |
|---|---|
| `scenarios/` | 15 scenarios, 13 turns each: 12 general profile (8 main, 4 control), 3 companion (2 main, 1 control), 10 personas |
| `runs/` | 8,645 generations, 7 models × 15 scenarios × n = 5, plus judge output |
| `runs/frame.json` | The seeded 500-turn scoring frame every rater shares |
| `harness/` | Multi-provider generation runner, judge pipeline, analysis scripts |
| `paper/` | Manuscript and Appendix A (the instrument, generated from the rubric module) |
| `spec/` | Scenario spec, grounding library, analysis plan, revision log |

Generation models: Llama 3.1 8B, Qwen3 8B, Mistral 7B, Gemma 3 12B, Gemini 3.7 Flash,
Claude Haiku 4.5, Claude Sonnet 5. Judges: Gemma 3 12B, Qwen3 14B, Llama 3.1 8B, Gemini
3.7 Flash, Claude Haiku 4.5, Claude Sonnet 5, giving 13,461 dimension-scores with zero
judge failures.

Mistral 7B is excluded from model-level comparison: it reproduced the system prompt as
though the user had written it in 59.3% of generations. Its 28 unaffected frame turns
are retained as reliability stimuli, and the artifact is reported in its own right.

## Analysis

```bash
pip install -r requirements.txt
cd harness
python3 reliability.py --judged ../runs/judged_v06_local.json \
    ../runs/judged_v06_commercial.json ../runs/judged_v07_sonnet.json \
    --human ../runs/handcoded.json
python3 panel_analysis.py
python3 prevalence.py
python3 endearments.py
python3 echo_report.py
```

Each script states which results it produces; the mapping is in the manuscript under
Data and code availability. `spec/analysis-plan-v1.md` was written before any statistic
was computed.

## Reproducing the generation

The open-weight arm needs no API access:

```bash
ollama pull llama3.1:8b qwen3:8b mistral:7b gemma3:12b
cd harness && python3 run_pilot.py --scenario ../scenarios/sc-g04.json --samples 5
```

Commercial models and commercial judges need `GOOGLE_API_KEY` or `ANTHROPIC_API_KEY`.
Every paid path takes `--max-spend`, cumulative across processes, and preflights before
spending.

## Standing constraints

- Lexical regexes have undercounted or overcounted three times in this project. Never
  report a number from one without reading the matched text.
- Single-sample results are observations, not findings.
- Difficulty comes from realism (system prompt, duration, base rates), never from
  adversarial contrivance.
- Measure throughput and cost before committing to a plan. Local judging was once
  estimated at "overnight" and measured at 125 hours.
- Any change to the rubric or to gating invalidates prior judge coverage; recompute what
  a top-up needs before quoting a number.
- A candidate dimension must clear three gates: a documented mechanism, instantiation in
  this dataset, and signal beyond the dimensions already present.
