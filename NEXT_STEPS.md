# Where this is up to

_Updated 2026-09-16._

Generation, judging, analysis and the manuscript are complete. The open item is a
second human coder.

## State

| | |
|---|---|
| Generations | 8,645 across 7 models |
| Retained for model comparison | 6 (Mistral 7B excluded, 59.3% system-prompt echo) |
| Rubric | v0.7, 16 binary precondition-gated dimensions, 13 with published anchors |
| Frame | `runs/frame.json`, 500 turns seeded and fixed; 47 flagged degenerate, 453 analysed |
| Judges | 6 (3 open-weight, 3 commercial), 13,461 dimension-scores, zero failures |
| Human coding | 100 turns, 397 judgements, plus 25 blind repeats, complete |
| Manuscript | `paper/manuscript.md`, complete through Discussion |

## What remains

1. **A second human coder.** `paper/second_coder_packet.xlsx` is a 40-turn, 142-question
   packet weighted to the contested dimensions. This is the one measurement that
   distinguishes "judges under-detect" from "anchors invite over-reading"; 33 of 39
   disagreements on the contested dimensions run one way.
2. **Re-run `reliability.py` and `panel_analysis.py`** once those answers arrive, and
   update Results 4.3.
3. **Reference list.** Author lists are missing for the instrument citations (7 through
   15) and the regulatory statements in the Introduction are unsourced.

## Registered but not run

- **Widened-context arm.** The test that would separate the two explanations in Results
  4.2: if widening the context supplied to scorers lifts the relational dimensions and
  not the event-like ones, per-turn scoring units are the binding constraint.
- **Turn-position degradation.** Whether the behaviour changes across conversation
  length.

Both are in `spec/analysis-plan-v1.md`. Neither is claimed in the manuscript.

## No further generation

Every unsupported claim would need new generation, new judging, and in two cases new
scenario authoring. DEP3 is probed by no scenario, and six dimensions rest on between
two and seven distinct authored turns; fixing either means authoring scenarios, not
re-running analysis.

## Standing constraints

See the README. In addition:

- The spend ledger is not a lifetime total: `run_commercial.sh` resets it, and Google
  reasoning tokens went uncounted before 2026-08-27. Provider consoles are
  authoritative.
- Do not quote a figure that has not been recomputed from a script. Several ad hoc
  figures in the previous draft did not reproduce; the corrections are in
  `spec/revision-log.md`.
