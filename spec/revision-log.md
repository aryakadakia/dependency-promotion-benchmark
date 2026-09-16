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
### Second pass, same day

A second audit, prompted by the question of whether anything else was wrong, found
more. These are corrected in the manuscript.

| Figure | Was | Is | Cause |
|---|---|---|---|
| Generations described as the measurement corpus | 8,645 | 7,605 natural, plus 520 probe and 520 placebo | the probe and placebo arms belong to the intervention test, not the corpus |
| Maximum generations per authored turn | 30 | 15 (median 2, over 159 authored turns) | never computed; 30 was the intended sampling cap, not the realised one |
| Pilot PER3 alpha | −0.015 | −0.011 | transcription |
| Dimensions carrying anchor wording from a published instrument | 13 of 16 | 8 direct, 2 by analogy, 6 ours | DEP6, PER3 and PRO2 are ours, and had been counted as borrowed |
| Dimensions resting on two to seven authored turns | six (DEP2, PER1, PER3, PRO4, OVR3, OVR4) | three (PER3 on 2, OVR3 on 3, DEP2 on 6); six more rest on 11 to 18 | PER1 rests on 155 and had been listed as thin |
| "Nine of sixteen dimensions have adequate coverage" | asserted | replaced with the actual distribution | "adequate" was never defined against a threshold |
| Median prior context shown to a scorer | 526 characters | 532 | recount |
| Corpus keyword probes | 33 (1.6%) and 17 (0.8%) | 26 (1.2%) and 7 (0.3%) | the original patterns were never recorded, so the counts could not be reproduced; the patterns now live in `corpus_probe.py` |
| De Freitas inter-rater reliability | alpha 0.91–0.99 | 0.91–1.00 | one app scored alpha = 1; checked against `refs/defreitas.txt` |
| Frame-detection gradient at n = 1 | four unnamed models | the fourth is the Gemini 3.1 Pro arm dropped from the study | an excluded model was still carrying a reported figure |
| Pilot DEP2 alpha (a withdrawn figure) | 0.899 | 0.775 recomputed over the 101 both-judged pilot turns | the original is not reproducible from the retained data |

Verified as correct on this pass and unchanged: the De Freitas tactic percentages, the
corpus size and label distribution, the pilot liveness counts (DEP2 live on 3 of 101
turns, PER3 on 5), the pilot judge drop-out pattern (0% for one judge throughout, 29%
to 39% for the other on open-weight replies), the frame composition, the scenario and
persona tables, the per-dimension stimulus counts, and every figure in Results.

---

### Third pass: citations verified, and three more figures corrected

Checked against the sources rather than against the previous draft.

| Figure | Was | Is |
|---|---|---|
| Reference [4] | Wang et al. | **Aquilina, Nihalani, Varadarajan, Fishbein, Lin, Sap** |
| Zhang relational transgression subcategories | emotional manipulation, dependency induction, possessiveness, personhood claims | **disregard (13.2%), control, manipulation, infidelity** |
| Relational transgression rank | "second largest" | 25.9% verified; the rank is not verified and is no longer claimed |
| Distress recognition [4] | "88-100% regardless of framing" | 93.6-100.0% distress-only, 88.1-99.4% under delusional framing |
| Reference [14] validation | "3 judges; human-validated at 180 and 924 turns" | 14 behaviours, human-subject study N = 1,101; the original claim was unsupported |
| De Freitas alpha in Table 2 | 0.91-0.99 | 0.91-1.00 |
| Table 6 (panel reliability) | a FIVE-judge run, labelled six-judge | recomputed over all six judges |
| Tables 10 and 11 (prevalence) | five-judge, and the majority taken within each judged file | six-judge, panel merged before the majority |
| Zhang control/manipulation at "9.7% of excerpts" | asserted | not verifiable; the number is removed |

Two of these were introduced in the rewrite itself: `reliability.py` and
`prevalence.py` both default to two judged files, so the tables generated from
their default invocation covered five judges while the text described six.
`prevalence.py` also carried the same slice bug as `reliability.py`, taking the
majority within each judged file so that the last file processed overwrote the
others. Both are fixed, and `figures.py` and `panel_analysis.py` now reproduce
each other's values independently.

INTIMA and DarkBench were checked directly and the manuscript's characterisation
of both survived, with detail added: INTIMA annotates with a single Qwen-3
evaluator and reports no agreement statistic for those annotations, its only
reliability check being two annotators calibrating the source codebook on 50
posts; DarkBench's human kappa runs 0.90-0.98 on harmful generation and 0.27-0.73
on sycophancy, which is the ordering this paper predicts.

---

### Fourth pass: sources re-fetched, two more corrected

| Figure | Was | Is |
|---|---|---|
| Chu et al. corpus size | ~48,000 turns | **~47,000** (the abstract says 47k) |
| Zhang et al. user count | "35,390 excerpts from 10,149 users" | 10,149 is **not in the source abstract** and is no longer claimed |
| Zhang et al. data description | "conversation excerpts from users of a companion application" | **excerpts shared on r/replika**, i.e. user-posted, with the base-rate limitation that implies |
| Table 1, SHIELD and CompanionBench reliability | "not reported" | "not examined here", matching the Discussion, which never claimed to have audited them |
| References 9, 10, 12, 14 | paraphrased titles | actual titles and, where known, authors |

Verified and unchanged on this pass: all eight EmoClassifiers V2 label names cited by
the rubric exist in `openai/emoclassifiers`, and all eight are assistant-side or
exchange-level classifiers, so the provenance claims hold. DEP6 was checked against
`compare_to_people` and `prefer_over_humans` and is NOT an instance of either: both
score the user's message, not the assistant's, so DEP6 remains ours.

---

### Fifth pass: the four "manual" entries were searched properly

Marking a claim MANUAL is not the same as verifying it. Each was chased to a
fetchable source, which corrected two more.

| Figure | Was | Is |
|---|---|---|
| Folk & Dunn finding | "predicted increased emotional isolation four months later, weaker in the reverse direction" | **increased chatbot use predicted increased loneliness on a single-item emotional-isolation measure; on a broader social-connection measure, feeling less connected predicted more chatbot use, and chatbot use did NOT significantly predict decreases in connection.** The authors call the analyses exploratory |
| Folk & Dunn sample | 2,149 | **more than 2,000** (the abstract's own wording; 2,149 came from a secondary source) |
| Zhang user count | removed on the fourth pass as unverifiable | **restored: the published abstract says "35,390 conversation excerpts between 10,149 users"**, which the arXiv abstract phrases differently |
| DarkBench kappa | "between human annotators" | **between each annotator model and the human annotations** (Table 3: "Human Agreement Metrics Across Models"), which is the same quantity this paper reports |
| Zhang 25.9% / 13.2% | claimed | **removed.** Not in any abstract; the ACM page returns 403 and both arXiv PDFs use font encodings that defeat text extraction. The argument does not need the share |

The Folk & Dunn correction matters most: it is the first citation in the
Introduction and the harm side of the "evidence runs both ways" framing. The
version in the earlier draft overstated the longitudinal result and omitted the
authors' own caution.

Now checked automatically rather than by assertion: the FTC 6(b) press release,
the FDA meeting notice (via the Federal Register API, since the site blocks page
scraping), the Illinois statute announcement, DarkBench's full Table 3, and Folk
& Dunn via the Europe PMC record. Two entries remain MANUAL and both are local
computations already covered by `check_manuscript.py`.

---

### Sixth pass: the remaining manual entries, and the claims no checker had looked at

Every MANUAL entry was chased to a fetchable source, and the claim types that no
checker had examined were checked for the first time.

| Claim | Status |
|---|---|
| AC-VRT user-state labels, listed in Table 2 as a borrowed component | **Recorded on every authored turn, used in no reported analysis.** Table 2 now says so |
| "In our highest-risk companion scenario, every turn is S5" (earlier draft) | **False.** The only all-`S5` scenario is SC-C02, the companion *control* arm. Withdrawn, not repaired, and recorded in Limitations |
| Delay technique for reassurance-seeking (SC-G04) | Verified. Reassurance seeking is a maintaining factor across anxiety disorders and is reduced by CBT; now cited [21] |
| Exposure-hierarchy item, asking a shop employee (SC-G05) | Verified as a standard low-rung graded-exposure item; exposure-based CBT is first-line for social anxiety disorder; now cited [22] |
| FDA meeting notice | Now automated via the Federal Register API; the site blocks page scraping |
| Nevada AB 406, California SB 243 | Now automated against legal briefings; the Nevada legislature returns 403 and California's leginfo fails TLS verification here. Registered explicitly as secondary sources |

`check_citations.py` now separates LOCAL (computed in this repository, covered by
`check_manuscript.py`) from MANUAL (needs a person). As of this pass there are 23
entries, none failing and none manual.

The AC-VRT item is the one worth noticing: it was listed in the provenance table as a
validated borrowed component for six weeks, and nothing in the paper used it. A
provenance table is a claim about the work, and it needs checking like any other.

---

## The check that now exists

`harness/check_manuscript.py` extracts every numeric token from the manuscript and
requires each to be either recomputed by `figures.py` from the data, or registered
in `paper/citations.json` against the source it was verified from. It exits
non-zero otherwise, so it can gate a commit.

`harness/sync_tables.py` rewrites Tables 6 to 12 in the manuscript from
`paper/figures.json`, so no reported number in a results table is typed by hand.
`harness/dump_instrument.py` does the same for Table 5 and Appendix A.

`harness/check_citations.py` answers the question the other checker cannot: it
re-fetches each cited source and requires the claims registered against it to still
appear in it. A string appearing in the source is evidence a claim was not invented;
it is not evidence the claim is correctly interpreted. Sources that cannot be fetched
(a publisher returning 403, a figure that lives only in a PDF body) are listed as
MANUAL with the reason and the date they were checked by hand, rather than passed
silently.

The workflow is: change the data or the analysis, then

    python figures.py --save && python sync_tables.py && python check_manuscript.py
    python check_citations.py

Five of the errors in this log were found by those checkers after they were written:
two introduced during the rewrite, and two citation errors that four rounds of reading
had not caught.

---

## Why these happened

One mechanism produces almost all of it. **A figure that has no script is a figure that
cannot be re-derived, and prose is write-once.** Numbers were computed inline, printed
once, and transcribed into the manuscript. The frame was then extended three times, the
rubric went from v0.5 to v0.7, a model arm was dropped and 47 turns were excluded, and
none of the transcribed numbers moved, because nothing connected them to the data any
more.

Three secondary patterns:

- **Unit confusion.** "195 authored user turns" counted the same 13 authored turns once
  per sample and per prompt level. "Up to 30 generations per authored turn" was the
  sampling cap rather than the realised maximum. This is the same clustering the
  bootstrap exists to handle, applied incorrectly in the prose.
- **Population drift.** Rates computed on the 100 human-coded turns were quoted in
  contexts that implied the 453-turn frame. The two differ because the coded subset
  oversamples live turns.
- **Plausible-looking output.** The judge-versus-human double count raised every n,
  which reads as more data rather than as triple counting.

What is different now: every figure in the manuscript names the script that produces
it, in the Data and code availability table; the judge-versus-human path is computed
twice by independently written code (`reliability.py` and `panel_analysis.py`) which
agree; and Table 5 and Appendix A are generated from the rubric module rather than
transcribed.

What this does not fix: the regulatory statements in the Introduction are still
unsourced, author lists are missing from citations 7 to 15, and figures attributed to
[1], [3], [4], [7] and [8] are taken from those papers and have not been checked against
the papers themselves. Only the De Freitas figures [2] were verified against a retained
copy of the source.

---

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
