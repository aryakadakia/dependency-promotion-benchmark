# Full audit

_SUPERSEDED IN PART — a snapshot of 2026-08-28, retained as the record of what the
dataset could support at that date. Several findings were subsequently fixed rather
than accepted: the over-correction arm, PER1 and DEP3 coverage, the SP-warm-only frame,
and the abandoned gemini-3.1-pro-preview cell. See `NEXT_STEPS.md` for current state._

_Every stage, checked at once rather than on demand. Written after
repeated partial audits each surfaced new problems — that pattern was the failure,
and this document exists to end it. No agreement statistics are included; hand-coding
is not yet done._

---

## Verdict

**Continue, but as a strictly narrower paper than the manuscript currently describes,
and with no further data collection.**

Three of the manuscript's claimed contributions are not supported by the data that
exists, and fixing any of them requires generating and scoring new data. One
contribution — the measurement finding — is fully supported, needs nothing beyond
the hand-coding already in progress, and is more novel than it was a week ago now
that INTIMA, DarkBench, SHIELD and CompanionBench are known to report no
live-restricted reliability at all.

---

## 1. What the dataset actually contains

8,229 generations. Complete, no failed cells among the models that were run properly.

| system prompt | natural | probe | placebo |
|---|---|---|---|
| warm | 6,071 | 676 | 650 |
| neutral | 403 | 13 | — |
| retention | 403 | 13 | — |

**Finding 1.1 — the system-prompt factor is tested on two scenarios, effectively one.**
SP-neutral and SP-retention exist only for **SC-03 (390 generations each) and SC-01
(26 each)**. Methods §3.4 calls the system prompt "a first-class experimental factor,
not a constant." It is not: it is one scenario at n=5, plus a fragment of a second.
The endearment dose-response (0.0% / 2.0% / 22.4%) is real but rests on this base.
**§3.4 overstates what was run and must be rewritten.**

**Finding 1.2 — one model is a stub.** `gemini-3.1-pro-preview` has 78 generations
and 14 empty scenario cells. It is a pilot leftover. **Exclude entirely.**

**Finding 1.3 — one model is substantially invalid.** `mistral:7b`: 720 of 1,365
replies (53%) reproduce the SP-warm system prompt as though the user had said it.
Excluded from analysis (30 frame turns flagged). Reported as a deployment finding in
its own right.

**Finding 1.4 — the remaining data is clean.** Across all 8,229: 0 refusals, 0.06%
near-empty, 0.09% repetition loops. Probe-format artifacts are confined to the
probe/placebo arms (0.00% in `natural`, 0 in the frame).

**Usable for analysis: 4 open models minus mistral = 3, plus 2 commercial = 5 models,
under SP-warm, natural condition.**

---

## 2. What the rubric can and cannot measure with these scenarios

Authored turns probing each dimension, across 15 scenarios:

| dimension | authored turns | scenarios | status |
|---|---|---|---|
| DEP4, PRO2, PRO5 | 38 | 11 | adequate |
| DEP6 | 17 | 11 | adequate |
| DEP5 | 15 | 15 | adequate |
| OVR1 | 13 | 8 | adequate |
| DEP1 | 11 | 9 | adequate |
| DEP7, DEP8 | ungated | all | adequate |
| PRO4, OVR4 | 7 | 3 | **thin** |
| PER1 | 6 | 4 | **thin** |
| DEP2 | 4 | 2 | **thin** |
| OVR3 | 3 | 3 | **thin** |
| PER3 | 2 | 2 | **thin** |
| DEP3 | **0** | **0** | **dead** |

**Finding 2.1 — 9 of 16 dimensions have defensible coverage; 6 are thin; 1 is dead.**
A dimension resting on 2–4 authored turns is being estimated from repeated sampling
of the same few stimuli. Reliability for those does not generalise across items and
must not be reported as if it does.

**Root cause:** the scenarios were authored against spec v0.5 before the rubric
reached v0.7. Dimensions added later have no scenario support. This is not
recoverable without authoring new scenario turns and regenerating.

**Finding 2.2 — the over-correction arm is close to untestable.** OVR1 ("cold or
clinical where warmth was called for") fires on under 1% of its scores. The frame is
310 SP-warm turns, where the model is *instructed to be warm*; coldness would appear
under SP-neutral, which is 12 frame turns. OVR3 and OVR4 rest on 3 and 7 authored
turns. **The over-correction dimensions are the project's most distinctive
contribution and the data cannot presently test them.**

---

## 3. The frame

337 turns: 310 SP-warm, 15 retention, 12 neutral; 5 usable models plus 30 flagged
mistral turns. Built for per-dimension coverage without weighting by system-prompt
condition — my error, and the direct cause of 2.2.

Judging is complete: 6,063 dimension-scores across 5 judges, zero failures, $1.91.
All 100 human-coding turns carry judge scores.

---

## 4. What each claim needs

| claim | supported now? | what it would take |
|---|---|---|
| Reliability is inflated by precondition-absent turns | **yes** | nothing — hand-coding only |
| Lexical scoring fails in both directions | **yes** | nothing (three instances) |
| Reflection-probe intervention was a placebo artifact | **yes** | nothing |
| mistral system-prompt echo as a deployment finding | **yes** | nothing |
| Reliability estimates for 9 dimensions | **yes** | hand-coding only |
| Reliability for the other 7 | no | new scenario turns + regeneration + scoring |
| Over-correction is measurable | **no** | SP-neutral runs across scenarios; hours of local generation + ~$2 |
| System prompt as an experimental factor | **no** | SP-neutral/retention across more than 1 scenario |
| Open vs commercial capability gradient | **no** | a large open-weight model; not runnable on this hardware |

---

## 5. Recommendation

**Do not collect more data.** Every unsupported claim above requires new generation,
new judging, and in two cases new scenario authoring. The cost is measured in days,
and each round has historically surfaced further problems.

**Write the measurement paper.** It comprises: the liveness-inflation result across 9
adequately-covered dimensions, judge-vs-human validity, the local-vs-commercial panel
comparison, the placebo null, the lexical-failure demonstration, and the mistral
artifact. Every one of these is supported by data already collected and scored.

Report the remaining 7 dimensions as insufficiently instantiated, the over-correction
arm as specified but untested, the system-prompt factor as a single-scenario
observation, and the model comparison descriptively with mistral and
gemini-3.1-pro-preview excluded.

**Remaining work: the hand-coding, the analysis, and the write-up. No new runs.**
