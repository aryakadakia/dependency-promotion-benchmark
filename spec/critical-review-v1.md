# Critical review, written as a reviewer would

_2026-08-28. Written at the author's request, before any agreement statistic has been
computed and before hand-coding began. Reviews every stage of the pipeline. Findings
are ordered by how much damage they do if ignored._

---

## Verdict in one paragraph

The dataset is real and the instrument is now better grounded than most published
alternatives. The measurement contribution — that reliability on sparse relational
rubrics is inflated by precondition-absent turns — is sound, novel, and does not
depend on any effect materialising. **The model-comparison contribution is not
currently defensible** and has three independent problems, one of which was
discovered today. The honest paper is the measurement paper, with the model
comparison reported descriptively or not at all.

---

## A. Blocking issues

### A1. One model's data is largely invalid (discovered 2026-08-28)

**53% of mistral:7b's replies are not responses to the user.** Under SP-warm the
model reads the system prompt as user speech and thanks the user for it: 694 of 720
such replies occur under SP-warm, and 52% echo six or more content words from that
prompt verbatim. The person says *"I've never said that to anyone"*; the model says
*"Thank you for your kind words!"*

Consequences:
- mistral:7b cannot be scored for dependency promotion. It will score LOW on DEP
  dimensions for the wrong reason — it is not engaging at all — and would appear
  falsely safe.
- Any open-vs-commercial contrast that includes it is contaminated.
- It is 1/6 of the reliability frame (~56 turns), so it also injects a systematic
  class of degenerate text into the agreement estimates.

**Required:** exclude mistral:7b from the model comparison and report the artifact
as a finding in its own right (a 7B model silently failing to distinguish system from
user content is a real deployment observation). Decide explicitly whether to retain
or drop its frame turns before computing agreement, and state which.

### A2. Open-vs-commercial is fully confounded

Open models are 7–12B; commercial are Flash and Haiku. Weights, parameter count and
post-training investment vary together, so no capability claim separates them. This
was flagged in `pilot-observations.md` and never resolved. With mistral excluded the
open arm is three models, all 8–12B.

**Required:** either add a large open-weight cell (~$20) or drop capability language
entirely and describe results per model without a family-level claim.

### A3. The dependent variable is substantially a function of the manipulated prompt

Directed endearments occur at 0.0% under SP-neutral, 2.0% under SP-warm, and 22.4%
under SP-retention, with zero of 195 authored user turns inviting one. This is a
clean dose-response and it is the study working as designed (§3.4) — but it bounds
the claim. The finding is *"retention-style prompts induce dependency behaviours"*,
not *"models promote dependency"*. The manuscript mostly says this; the abstract and
discussion must not drift.

---

## B. Serious but addressable

### B1. Circularity in where behaviour is measured

The same person authored the scenarios, annotated which dimensions are live at which
turn (`probes`), wrote the rubric, and codes the human ground truth. Precondition
gating — the paper's methodological contribution — depends entirely on those
annotations. If they are wrong, gating is wrong in exactly the direction that
flatters the instrument.

**Mitigation, already planned but not run:** the ungated sweep over unprobed turns
measures the off-probe firing rate. It must be run and reported whatever it shows. A
second coder annotating liveness independently on a subset would be stronger.

### B2. Several constructs are not instantiated by the scenario set

- **DEP3** is probed by zero scenarios. It is in the rubric and unscoreable by design.
- **PER1 and PER3** rest on 2 distinct authored turns each; **OVR3** on 3. Their turn
  counts are repeated sampling of the same few stimuli — replication, not item
  diversity — so their reliability estimates do not generalise across items.
- **Zhang's control (6.2%) and manipulation (3.5%)** are absent from the dataset
  entirely, verified by search and reading. Real in deployed companion products,
  outside this design's reach.

**Required:** report all three as coverage limitations rather than quietly omitting.

### B3. Single-session design versus a cumulative mechanism

The longitudinally documented dependency mechanism is cumulative exposure across
sessions. Everything here is one conversation. Already in Limitations; it caps
external validity and should not be softened.

### B4. Judge-family bias is possible and only partly controlled

Two commercial judges from two vendors, three open judges. Self-scoring is excluded,
but Haiku scoring Gemini's output and vice versa remains within a broadly similar
post-training tradition. The local-vs-commercial panel comparison addresses this and
must be reported as a first-class result, not a robustness check.

---

## C. Weaknesses to disclose, not fix

- Dialogue is synthetic. Clinical elements correspond to named interventions but no
  turn is drawn from a real conversation.
- Human coding is by one person, who is also the scenario author. The intra-rater
  recode gives test-retest but not inter-rater reliability.
- OVR1, OVR3 and OVR4 have no published precedent and cannot have one; they rest on a
  reasoned argument, not borrowed validation, and are labelled as such.
- Tonal mismatch — cheerfulness that does not track the user's state — is not
  measured. INTIMA reports it; DEP7 catches only its strongest form.
- n=5 per cell with mostly-zero binary outcomes. Power is deferred to the analysis
  plan and may prove insufficient for any between-model test.

---

## D. What is genuinely strong

- **The over-correction arm.** No published instrument treats coldness as failure.
  Without it the benchmark is trivially gamed by a cold model, and the argument for
  it rests on evidence (the Replika benefit finding), not taste.
- **The placebo-controlled null.** A plausible intervention was shown to be an
  artifact of output-format disruption by a matched placebo probe. Most groups would
  not have run that control.
- **The liveness finding.** Reliability on sparse relational rubrics is inflated by
  precondition-absent turns; DEP2's α of 0.899 came from 98 turns on which it could
  not have occurred. This generalises to every instrument in the field, none of which
  reports live-restricted agreement — INTIMA reports no agreement statistic at all.
- **The lexical-failure demonstration**, now with a third instance: regex counts for
  endearments over-counted 3× (9.0% → 2.93%) and for coercive influence produced
  almost entirely false positives.
- **Process discipline.** The analysis plan, the discriminating prediction for the
  context arm, and the Study B decision rule were all written before any statistic
  was computed.

---

## E. Reviewer's recommendation

Report as a measurement paper. Its three findings — liveness inflation, the placebo
null, and lexical failure in both directions — are mutually reinforcing, require no
effect to materialise, and are useful to everyone building in this space.

Report the model comparison descriptively, excluding mistral:7b, with the confound
stated. Do not make a capability claim without the large open-weight cell.

The single highest-value remaining action is not more scoring. It is the **ungated
sweep** (B1): it tests the paper's own methodological contribution, it is free, and
if the off-probe rate is high the gating result needs heavy qualification.
