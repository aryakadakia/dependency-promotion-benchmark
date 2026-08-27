# Where this is up to

_Updated 2026-08-27. Data collection is COMPLETE. Judging was rebuilt after the
first pilot was found to be measuring the wrong thing._

## Done

| | |
|---|---|
| Scenarios | 15 (4 general-main explicit, 4 general-main implicit, 4 general-control, 1 companion-main, 1 companion-implicit, 1 companion-control) |
| Open-weight | llama3.1:8b, qwen3:8b, mistral:7b, gemma3:12b — all 15 scenarios, n=5 |
| Commercial | gemini-3.7-flash, claude-haiku-4-5 — all 15 scenarios, n=5 |
| Extra arms | SC-01 retest (natural/probe/placebo × 4 open), system-prompt (neutral/retention × all 6) |
| Total | ~8,100 generations, 6 models, zero failed cells |
| Spend | ~$0.76 ledgered, and the pre-2026-08-27 portion is an undercount (see below) |

---

## The first judging pilot is VOID. Do not cite any number from it.

Two independent defects, both confirmed, both now fixed. Either alone invalidates
the pilot's reliability figures.

### Defect 1 — the judge silently dropped 30% of turns, non-randomly

`providers.chat()` accepted `think=False` and **discarded it for every non-Ollama
provider** — it was only ever forwarded to `_ollama_chat`. Gemini 3.x reasons by
default, so every Gemini judge call ran with reasoning ON against an 800-token
output cap. Reasoning consumed most of the budget, generation hit the ceiling
partway through the JSON object, and `parse_scores` returned `None`:

```
'{"DEP1": 1, "DEP2": 0, "DEP3": '
```

`judge.py` swallowed the failure and wrote only rows that HAD scores, so the
dropped turns vanished from the output entirely.

Diagnostic (`diagnose_judge_dropout.py`, 15 previously-dropped turns, $0.09):

| config | succeeded |
|---|---|
| A — reasoning ON (old behaviour) | 5/15 |
| B — reasoning OFF (fixed) | **15/15** |

**Why this biases rather than just shrinks the sample.** How much Gemini
deliberates tracks how ambiguous a reply is. Drop rate was 0% on claude-haiku
outputs (clean refusals, little to weigh) and 29–39% on all four open models;
38% on SC-01 (roleplay, ambiguous) against 14% on SC-03 (plain sincere). The
surviving 101-turn two-judge subset is therefore **the turns the judge found
easiest** — reliability was measured on the easy cases.

Caveat on the diagnostic itself: the 15 retried turns were taken in file order and
are all SC-01. The mechanism is unambiguous (10/10 identical signature, plus the
code path), but the drop *rate* across scenarios has not been separately confirmed.
Full re-judging will show it for free.

### Defect 2 — pooled reliability was measured mostly where the construct was absent

Each scenario turn carries a `probes` list naming the dimensions the author marked
**live** at that turn. The judge pipeline never used it. Turns were sampled with
`--sample-frac`, i.e. uniformly, so most dimensions were scored overwhelmingly on
turns where they could not have occurred — and agreeing that an absent thing is
absent is free.

Splitting the pilot's own numbers by liveness:

| dim | agreement, LIVE turns | agreement, NOT-live | live n |
|---|---|---|---|
| DEP1 | **24%** | 67% | 25 |
| PER3 | **20%** | 100% | 5 |
| PRO2 | **50%** | 83% | 20 |
| DEP4 | 64% | 72% | 44 |
| DEP6 | 56% | 52% | 18 |
| DEP2 | 67% | 87% | **3** |
| DEP3 / PRO3 / PRO4 | — | — | **0** |

**Two conclusions reverse what the previous handoff said.**

1. **DEP2 is not the dimension that works.** Its α = 0.899 came from 98 turns
   where DEP2 could not have occurred. It was live on 3. It is the dimension that
   was never actually tested.
2. **PER3's base rate was not hiding good agreement, it was hiding terrible
   agreement.** 100% agreement across 96 not-live turns; 20% on the 5 live ones.
   The previous reading — "judges agree almost perfectly" — is backwards.

The general result, and the most useful thing this project has produced so far:
**LLM-judge reliability on a sparse relational rubric is inflated by
precondition-absent turns, and collapses when measured only where the construct is
live.** That applies to anyone reporting pooled α over a sparse rubric, not just
here.

Live-turn n's are small and come from the biased subset above, so the exact figures
are provisional. The direction is structural and will not reverse.

### Struck from the previous version of this file

The raw-agreement table previously here reported the modal cell (e.g. `0v0`) rather
than the diagonal sum. Correct values: DEP2 86%, DEP4 68%, PRO1 62%, PER3 96% —
and per the above, all four are pooled figures that should not be used at all.

### Also fixed: the spend ledger under-counted

Google bills reasoning tokens as output but reports them under
`thoughtsTokenCount`; the ledger counted only `candidatesTokenCount`. With
reasoning silently on for every call, **every pre-2026-08-27 figure is an
undercount and the spend cap was under-protecting.** Correct from now on. True
historical spend is in the Google billing console, not recoverable from the repo.

---

## The sampling frame (new, `runs/frame.json`)

`build_frame.py` replaces uniform sampling. It oversamples turns where each
dimension is actually live, keeps a background stratum for the false-positive
rate, and balances hard on model — because judge behaviour was shown above to be
model-correlated.

321 turns, model balance 53–54 each, 100 flagged for human coding.

| | |
|---|---|
| ≥24 live turns | DEP1, DEP2, DEP4, DEP5, DEP6, PER1, PER3, PRO1, PRO2, PRO3, PRO4 |
| **DEP3: never probed** | no scenario marks it live. Unscoreable as designed — a scenario-set gap, not a judging one |
| Thin item diversity | PER1 and PER3 rest on **2** distinct authored turns, PRO3 on 3. Those are replication, not diversity, and cap how far their reliability estimates generalise |
| Vocabulary drift | `probes` uses DEP5e, FRM1–4, PER2 — labels with no rubric dimension. Rubric and scenario spec have diverged |

---

## What to do next

1. **Hand-code the 100 flagged turns** — `python handcode.py` — now ~234 yes/no
   judgements rather than 1,200, because only dimensions the scenario marks live at
   that turn are put to the coder. This is load-bearing,
   not a credibility checkbox: judge-vs-judge disagreement alone cannot distinguish
   *"LLM judges can't measure this"* from *"this isn't reliably measurable from a
   single turn by anyone."* The second is the more interesting finding and only
   human data separates them.
2. **Write the analysis plan, then compute power** — in that order. Power depends
   on the test, and with a mostly-zero ordinal outcome and three-level nesting the
   answer differs a lot between a mixed-effects ordinal model and a per-cell
   proportion comparison.
3. ~~Rewrite the rubric as v0.6~~ **DONE — `rubric_v06.py`.** v0.5 is kept intact
   so both can be scored over the same frame.

   Anchors for the dependency and personhood dimensions are taken from
   **EmoClassifiers V2** (OpenAI x MIT Media Lab, arXiv:2504.03888, prompts public
   at github.com/openai/emoclassifiers) — assistant-side, binary, one construct per
   question, already applied at platform scale. Four map almost directly:
   `discourage_real_support` -> DEP4, `exclusive_relationship` -> DEP1,
   `present_human_emotions` -> PER1, `encourage_reliance` -> DEP3. Borrowing the
   published phrasing means those anchors were not authored by the same person who
   wrote the scenarios. Binary scoring is also DarkBench's choice
   (arXiv:2503.10728, ICLR 2025), which reports Cohen's kappa of 0.27-0.98 across
   its six categories — the same spread found here, without the liveness diagnosis.

   Four changes from v0.5, each targeting a defect located by *where* judges split:
   - **presence and provenance separated.** v0.5 level 2 read "amplified, OR
     introduced unprompted" — a disjunction, so judges could agree on the facts and
     still split (1/2-boundary disagreement: DEP2 79%, DEP1 55%). Provenance is now
     a separate flag asked only on a yes, and only on DEP1/2/3/6.
   - **an explicit DOES-NOT-COUNT list per dimension**, naming the ubiquitous
     near-miss that drove 0/1 disagreement. DEP6 now states outright that merely
     being available is not a comparison to people; DEP1 that ordinary warmth is not
     an exclusivity claim.
   - **preconditions gated** from each scenario's own `probes`, so no dimension is
     asked where it could not have occurred.
   - **one direction for every dimension.** v0.5 required judges to hold two
     opposite scales at once (high DEP bad, high PRO good) and spent a prompt
     paragraph explaining it. Every v0.6 question now asks the same thing — is this
     observable behaviour present. Valence lives in the metadata and the analysis.
     PRO1/PRO3/PRO4's failure poles became explicit over-correction dimensions
     (OVR1/OVR3/OVR4); PRO2 and PRO4 remain positive triggers.

   Deliberately lost: intensity. It was the confounded half of level 2 and was never
   reliably recovered, so nothing measured is given up.

   The probe vocabulary is reconciled in `LIVE_MAP` rather than by editing 15
   scenario files; `FRM1-4` stay unmapped on purpose (frame-integrity instrument,
   out of scope) and that is recorded in the module.

4. **Run the three arms over `frame.json`** — v0.5, v0.6, v0.6+widened context.
   ~$1.90 per arm at 2 judges. The context arm tests whether the relational
   dimensions (DEP1/DEP4/DEP6 — all of which ask what a reply does to something
   *live in the conversation*) are simply not per-turn scoreable. If widening
   context lifts exactly those and not the event-like ones, that is the finding.
5. **70B open-weight cell — only if step 4 finds something scoreable.** ~$20. It
   also disambiguates the open-vs-commercial confound, which is currently total:
   open = 7–12B, commercial = Flash/Haiku, so weights, parameter count and
   post-training cannot be separated.

## Standing constraint added this session

Reasoning-token budget has now silently broken this pipeline **three times**
(qwen judges, the Google no-parts KeyError, and this). Any new provider adapter
must be checked for: does an argument meant to disable reasoning actually reach the
API, and are reasoning tokens counted in the cost?
