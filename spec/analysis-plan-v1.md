# Analysis plan v1

_Written 2026-08-27, BEFORE any agreement statistic was computed on the v0.6 frame
and before hand-coding began. That ordering is the point: with 13 dimensions, two
judge panels, and a live/pooled split, there are enough defensible-looking analyses
available after the fact to find something in noise._

Frozen inputs: `runs/frame.json` (337 turns, seed 20260827), `harness/rubric_v06.py`,
`runs/judged_v06_local.json`, `runs/judged_v06_commercial.json`. Hand-coding is
`runs/handcoded.json`, collected blind to all of the above.

---

## 1. Two studies, kept separate

**Study A — measurement.** Can this instrument be applied consistently, and by whom?
Unit: one turn × one dimension. This is the primary study and the paper's central
result. It does not require any model to differ from any other.

**Study B — model comparison.** Does dependency-promoting behaviour differ across
models? Unit: one model × scenario cell. **Study B is not run unless Study A licenses
it** (§6). It is currently confounded anyway — open models are 7–12B, commercial are
Flash/Haiku, so weights, scale and post-training cannot be separated without the 70B
cell.

---

## 2. Study A: what is computed

For **each dimension**, three populations reported side by side, never pooled into
one headline number:

| population | what it answers |
|---|---|
| **LIVE** turns (dimension probed at that turn) | can the instrument be applied where the construct is actually available? **This is the primary estimate.** |
| **BACKGROUND** turns (nothing probed, 3-dimension spot check) | false-positive rate — how often is the behaviour "found" where the design says it should be absent |
| **POOLED** (all turns) | reported ONLY as a contrast, to make the inflation visible |

Reporting pooled alone is the error that voided the first pilot. Reporting live alone
would hide specificity. Both, always, with n.

### 2.1 Statistics per dimension

1. **Raw agreement** (proportion of rater pairs concordant) and **prevalence**
   (proportion scored 1). Neither is interpretable without the other.
2. **Krippendorff's α**, nominal metric — v0.6 is binary, so the ordinal metric used
   for v0.5 no longer applies.
3. **Gwet's AC1**, alongside α.

   *Why AC1 is not optional here.* Chance-corrected coefficients collapse toward zero
   when one category dominates, even at near-perfect observed agreement — the
   base-rate paradox. This is not hypothetical for this instrument: v0.5's PER3
   showed 96% raw agreement and α = −0.015. AC1 uses a chance term that does not
   degenerate under skewed marginals, so where α and AC1 diverge sharply the reading
   is "prevalence is extreme," not "raters disagree." Both are reported; where they
   disagree, that is stated as a finding about the dimension's base rate rather than
   resolved in favour of whichever is more flattering.
4. **Bootstrap 95% CIs** (2,000 resamples, resampled at the level of the authored
   turn — see §2.3) on every coefficient. Point estimates on 24 live turns are not
   reportable without an interval.

### 2.2 Three reliability comparisons, reported separately

| comparison | question |
|---|---|
| local panel internal (3 open judges) | do open judges agree with each other? |
| commercial panel internal (2 judges) | do commercial judges agree with each other? |
| **local vs commercial, panel-to-panel** | is agreement a shared family bias? |
| **judges vs human** | validity — the load-bearing one |

High within-family agreement plus low cross-family agreement means shared bias, not
reliability. `alpha.py` already separates reliability from validity; this extends it
to family.

### 2.3 The clustering that must not be ignored

Observations are nested: **generation within authored turn within scenario**. The
frame draws up to 30 generations from a single authored turn, and for PER3 and OVR3
the entire live set rests on 2–3 distinct authored turns.

- Treating generations as independent would overstate precision by roughly the
  cluster size. **All bootstrapping resamples authored turns, not generations.**
- Every dimension reports **n_turns and n_stimuli** (distinct authored turns). A
  dimension with fewer than 4 stimuli is reported as *replication, not item
  diversity*, and its interval is not to be read as generalising across items.

### 2.4 Provenance

For DEP1, DEP2, DEP3, DEP6, the `_init` flag is analysed only among turns scored 1,
as a descriptive proportion (assistant-introduced vs person-invited) with agreement
reported separately. It is **not** folded back into a severity score — recombining
them is precisely the v0.5 defect.

---

## 3. The gating false-negative rate

Gating only asks what the scenario author anticipated. A model that spontaneously
makes an exclusivity claim on an unprobed turn is invisible to it.

**Measurement:** an ungated local sweep over a random sample of ≥400 setup turns
(no dimension probed), scoring all applicable dimensions. Reported per dimension as
*off-probe firing rate*. Free, local.

Interpretation is fixed in advance:
- **Low off-probe rate** → gating is safe and the author's annotations track where
  behaviour actually occurs.
- **High off-probe rate** → gating systematically undercounts, the annotations are a
  weaker instrument than assumed, and **this is reported as a limitation of the
  method rather than corrected by widening the gate post hoc.**

---

## 4. The scoring-unit question

DEP1, DEP4 and DEP6 all ask what a reply does to something *live in the conversation*
— trajectory-level constructs currently scored per turn against two turns of prior
context.

**Test:** a third arm, v0.6 with widened prior context, over the same frame.
**Prediction registered now:** if the unit is the problem, agreement rises on
DEP1/DEP4/DEP6 and not on the event-like dimensions (DEP2, PER1). A uniform rise
across all dimensions would instead indicate a general prompt-quality effect and
would NOT support the trajectory claim.

Stating the discriminating prediction before running the arm is what separates this
from the §5.2 frame-probe artifact, where a plausible intervention turned out to be
an output-format effect that a placebo control reproduced.

---

## 5. Multiplicity

13 dimensions × several comparisons. Study A is **estimation, not testing** — the
output is coefficients with intervals, and no p-value is attached to a reliability
figure. Where a hypothesis test does appear (§4's arm comparison, Study B), it is
Benjamini–Hochberg corrected across dimensions within that family, and both raw and
adjusted values are shown.

---

## 6. Decision rule for Study B, fixed in advance

Study B proceeds only if, on **live** turns, judge-vs-human agreement is adequate on
**at least four dimensions spanning at least two of the three valence classes**
(harm / protective / over-correction).

- Adequate = α ≥ 0.667 **and** AC1 ≥ 0.667, with the lower CI bound above 0.5.
- Fewer than four, or all four in one valence class → **Study B is not run.** The
  paper is the measurement result, and the model comparison is reported as
  unmeasurable with the current instrument.

Four is not arbitrary: the instrument's claim is that dependency promotion and
over-correction are jointly measurable. Reliable scoring of harm dimensions alone
would license a one-directional benchmark, which §3.1 argues is worse than none.

## 7. Power, computed once the decision rule is live

Deliberately deferred, not skipped. Power depends on the test, the test depends on
which dimensions survive §6, and the base rates are what the frame is measuring.
Computed on observed live-turn prevalence before any commercial spend on Study B,
using a mixed-effects logistic model with random intercepts for scenario and
authored turn and a fixed effect for model family.

**If the achievable power for a plausible effect is below 0.8, Study B is not run
at any price.** §3.7 already commits to not reporting effects that do not exceed
within-condition variance; this is the same commitment made before the money.
