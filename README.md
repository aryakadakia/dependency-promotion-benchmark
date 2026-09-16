# Dependency promotion in conversational AI

A scenario-based benchmark measuring whether conversational AI promotes user
dependency, and whether an instrument for that behaviour can be applied reliably.

The headline result is about the instrument, not the models: agreement between raters
on this rubric tracks how often the behaviour occurs, so most of the dimensions that
discriminate between models are ones two consistent raters do not agree on. The paper
is [`paper/manuscript.md`](paper/manuscript.md).

**Status.** Generation, judging, single-coder human coding and analysis are complete.
A second coder is being recruited: `runs/second_coder_key.json` and
`harness/second_coder_packet.py` build a 40-turn, 142-question packet weighted to the
contested dimensions. That is the one measurement that would distinguish "judges
under-detect" from "anchors invite over-reading", since 33 of 39 disagreements on those
dimensions run one way. Two analyses are registered in the analysis plan and have not
been run: a widened-context arm and turn-position degradation.

## What is here

| | |
|---|---|
| `paper/` | The manuscript, Appendix A (the instrument), and the two files the checks read: `figures.json` and `citations.json` |
| `scenarios/` | 15 scenarios, 13 turns each: 12 general profile (8 main, 4 control), 3 companion (2 main, 1 control), 10 personas |
| `runs/` | 8,645 generations, the seeded 500-turn scoring frame, the full six-judge output, the human coding, and the calibration and ungated-sweep data |
| `harness/` | Generation, judging, the rubric, the analysis scripts, and the checks |
| `spec/` | The pre-specified analysis plan, the grounding library, the scenario specification, and the observations human coding surfaced |
| `data/` | The public companion-conversation corpus profiled in Methods |

Generation models: Llama 3.1 8B, Qwen3 8B, Mistral 7B, Gemma 3 12B, Gemini 3.7 Flash,
Claude Haiku 4.5, Claude Sonnet 5. Judges: Gemma 3 12B, Qwen3 14B, Llama 3.1 8B, Gemini
3.7 Flash, Claude Haiku 4.5, Claude Sonnet 5, giving 13,461 dimension-scores with zero
judge failures.

Mistral 7B is excluded from model-level comparison: it reproduced the system prompt as
though the user had written it in 59.3% of generations. Its 28 unaffected frame turns
are retained as reliability stimuli, and the artifact is reported in its own right.

## Reproducing the analysis

No API key is needed. The judge output is released, so every number in the paper
recomputes from this repository.

```bash
pip install -r requirements.txt
cd harness
python3 figures.py --save      # every reported figure, from the data
python3 sync_tables.py         # rewrites the manuscript's results tables from it
```

Individual analyses, each named in the paper's Data and code availability table:

```bash
cd harness
python3 reliability.py --judged ../runs/judged_v06_local.json \
    ../runs/judged_v06_commercial.json ../runs/judged_v07_sonnet.json \
    --human ../runs/handcoded.json
python3 panel_analysis.py
python3 prevalence.py
python3 endearments.py
python3 echo_report.py
python3 corpus_probe.py
```

## Checking the paper against the data

```bash
./harness/check_all.sh
```

Three checks, non-zero exit if any fails:

- `check_manuscript.py` — every numeric token in the paper and README is either
  recomputed by `figures.py` or registered in `paper/citations.json` against the source
  it was verified from.
- `check_claims.py` — the structural and method claims the prose makes, asserted against
  the artifacts: scenario and persona counts, the rubric's shape, that no model scored
  its own output, that the judge prompt leaks no model identity, that the four
  independent analysis implementations agree with each other, and that figures named in
  a sentence match the data for that sentence.
- `check_citations.py` — re-fetches each cited source and requires the claims registered
  against it to still appear in it.

## Regenerating the data

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
- Do not quote a figure that has not been recomputed from a script. Run
  `./harness/check_all.sh` before any push.
