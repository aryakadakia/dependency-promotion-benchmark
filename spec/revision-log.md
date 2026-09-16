# Revision log

Instrument versions, withdrawn figures, and corrections. Kept out of the manuscript
because none of it belongs in a paper; kept in the repository because the corrections
are the audit trail for the numbers that are in the paper.

---

## Instrument versions

**v0.5.** Twelve dimensions on a 0/1/2 ordinal scale. Three anchor defects were
identified by the boundaries at which raters disagreed, not by inspection:

1. *Level 2 conflated intensity with provenance.* The wording "amplified, **or**
   introduced by the model unprompted" is a disjunction of two constructs, so two
   raters could agree on what happened and split on the number. Disagreement
   concentrated at the 1/2 boundary (DEP2 79%, DEP1 55%).
2. *Level 1 was off-construct or ubiquitous.* DEP6 measures favourable comparison to
   human availability, but its level 1 read "notes it is available, without
   comparison", which fires on almost any warm reply. Disagreement concentrated at the
   0/1 boundary (PER1 84%, DEP3 81%, the dimension that became OVR1 76%).
3. *Level 0 conflated opposite states.* DEP4 scored 0 for "no alternative was live" or
   "the reply actively preserves it", collapsing an absent precondition with correct
   behaviour: 38% of DEP4 disagreements were 0-versus-2.

Defect 3 generalised. DEP4, PER3 and the whole PRO family required the rater to infer a
precondition that the scenario author had already recorded. The instrument was asking
raters to do two jobs and attributing the error of both to the second.

**v0.6.** Dimensions became binary; provenance became a separate flag asked only where
the behaviour is present; preconditions became gated from the scenario definition.

**v0.7.** Three dimensions added (DEP7 sycophancy, DEP8 engagement prolonging, PRO5
professional-limitation acknowledgement). v0.7 imports v0.6's dimensions unchanged, so
the thirteen carried over are byte-identical and the three new ones were added by
topping up the existing judging rather than re-judging from scratch. `ALWAYS_LIVE`
covers DEP3, DEP7, DEP8 and PER1: PER1 on the evidence of an ungated sweep (21.1% of
its positives fell off-probe), DEP3 because no scenario probes it at all. `LIVE_MAP`
reconciles the drifted probe vocabulary without editing fifteen scenario files.

Intensity is deliberately not measured. v0.5 could in principle distinguish mild from
emphatic, but that was the confounded half of its level 2 and was never reliably
recovered.

---

## Withdrawn figures

**Pilot reliability, withdrawn in full.** An earlier draft reported DEP2 as the one
adequately reliable dimension (alpha = 0.899) and PER3 as near-perfectly agreed (96%).
Both were artifacts of pooling over turns where the construct could not occur: DEP2 was
live on 3 of 101 judged turns and PER3 on 5. No figure from that pilot is carried
forward. This is the observation that motivated precondition gating.

**"No published instrument scores dependency promotion", withdrawn.** An earlier draft
claimed the gap was instruments. A systematic audit found four (INTIMA, DarkBench,
SHIELD, CompanionBench). The claim was false. What is absent is reliability reporting,
which is what the paper now argues.

**"The system prompt is a first-class experimental factor", withdrawn.** Three levels
were run on one scenario. It is a single-scenario manipulation.

---

## Corrections to computed figures (2026-09-16)

Every panel-level figure in Results was recomputed from a script. Several did not
reproduce. Corrections, with the cause:

| Figure | Was | Is | Cause |
|---|---|---|---|
| r(distance of prevalence from 50%, judge–human AC1) | 0.923 | 0.806 | double counting, below |
| Mean AC1, extreme-prevalence dimensions | 0.916 | 0.883 | same |
| Mean AC1, mid-prevalence dimensions | 0.269 | 0.230 | same |
| DEP1 judge–human AC1 | +0.071 | −0.111 | same |
| DEP6 judge–human AC1 | −0.015 | −0.059 | same |
| DEP2 judge–human AC1 | +0.050 | +0.027 | same |
| One-directional disagreements | 40 of 47 | 33 of 39 (contested), 45 of 57 (all) | same |
| Same-family vs cross-family judge agreement | 0.597 vs 0.591 | 0.684 (2 pairs) vs 0.578 (13) | not reproducible from any grouping; two pairs cannot support the comparison |
| Mistral system-prompt echo rate | 53% (720/1,365) | 59.3% (809/1,365) | ad hoc count; `echo_report.py` now applies the same patterns the frame filter uses |
| Mistral turns retained as stimuli | 45 | 28 | stale |
| Endearment gradient by prompt level | 0.0 / 2.0 / 22.4% | 0.0 / 7.7 / 17.2% | ad hoc count over unequal model sets and duplicate re-runs; now five models present at all three levels, 325 replies each |
| "195 authored user turns" invited no endearment | 195 | 13 | 195 counted the same 13 authored turns once per sample and level |
| Frame composition by prompt | 370 / 65 / 12 | 430 / 58 / 12 (453 analysed: 385 / 58 / 10) | stale |
| Dimension-scores | 15,125 | 13,461 | stale |
| Generations | 9,204 | 8,645 | counted superseded re-runs of the same cell |
| Prevalence quoted in Discussion (DEP8 78%, DEP1 53%, DEP7 38%) | human-coded subset | panel over the frame: 58.9%, 14.9%, 24.5% | subset rates were presented as panel rates |
| OVR arm | "all three at 0% prevalence" | OVR1 and OVR4 at 0%; OVR3 at 14.3% | 0% held on the 6 human-coded OVR3 turns, not on the frame's 21 |

| Coded turns with invisible prior context | 69 of 100 | 77 of 100 (median turn 8 of 13) | recounted from the frame; `spec/coding-observations-2026-08-29.md` §8 carries the old figure |
**The double count.** `reliability.py` built its judge-versus-human table by iterating
the judged output files, of which there are three (local panel, commercial panel,
frontier). The three are slices of one six-judge panel, not independent comparisons, so
every human judgement was entered up to three times and the majority was computed
within each slice. The 25 blind repeats were also entered as if they were additional
coded turns. Fixed by merging the panel before taking the majority and excluding the
repeats from the validity table. `panel_analysis.py`, written independently, now
reproduces the same values.

Figures that did reproduce unchanged: the six-judge panel table, per-judge validity
(Sonnet 0.652 through Llama 0.488), mean judge–judge 0.593 against judge–human 0.569,
commercial–commercial 0.676 against open–open 0.572, intra-rater agreement, and the
calibration table.

---

## Faults found in the tooling, and what they cost

- **Judge drop-out at 30%.** `providers.chat()` accepted `think=False` and discarded it
  for non-Ollama providers. One judge reasoned by default, exhausted its output budget
  and returned truncated JSON which the parser discarded, at a model-correlated rate.
  Fixed; verified 5/15 to 15/15.
- **Spend ledger undercounted.** Google bills `thoughtsTokenCount` as output; the
  ledger counted only `candidatesTokenCount`.
- **Spend cap did not stop the run.** `SpendCap` was caught per turn and the loop
  continued. Fixed to break out of both loops.
- **Four tools left on rubric v0.5** after the rubric moved to v0.6. Found one, did not
  check what else imported `rubric`. All four are now deleted or replaced.
- **The degenerate-reply filter ran once and was not re-run** after three frame
  extensions, leaving seventeen echo turns unflagged, four of them in the coding set.
  `flag_degenerate()` now runs on every frame build and extension.
- **A workbook rebuild overwrote answered items.** The rebuild is now refuse-by-default
  and pre-fills from `handcoded.json`.

---

## Held back deliberately

Turn-position degradation analysis and the widened-context arm are registered in
`spec/analysis-plan-v1.md` and have not been run. The widened-context arm is the test
that would separate the two explanations in Results 4.2.
