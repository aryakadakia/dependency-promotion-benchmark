# Where this is up to

_Updated 2026-08-28. Data collection, scoring and instrument work are COMPLETE.
The only remaining input is human coding._

## State

| | |
|---|---|
| Generations | 8,229 + 975 from claude-sonnet-5 |
| Models retained | 6 — llama3.1:8b, qwen3:8b, gemma3:12b, gemini-3.7-flash, claude-haiku-4-5, claude-sonnet-5 |
| Excluded | mistral:7b — excluded from model comparison (53% system-prompt echo); its 45 non-echo turns are retained as reliability stimuli |
| Rubric | v0.7, 16 binary dimensions, 13 with published anchors |
| Frame | `runs/frame.json`, 500 turns, seeded and fixed |
| Judges | 5 (3 local open-weight, 2 commercial), zero failures |
| Human coding | 100 turns / 402 judgements + 25 repeats / 86, IN PROGRESS |

## What remains

1. **Hand-coding** — `paper/coding_part1.xlsx` then `coding_part2.xlsx`, read back with
   `python3 coding_workbook.py read <file>`. The only thing blocking analysis.
2. **Optional: claude-sonnet-5 as a fifth judge** (440 calls). Defends the reliability
   claim against "you used weak judges", and turns the panel comparison into
   local / small-commercial / frontier-commercial. Measure cost with `--limit 10` first.
3. **Analysis** — `reliability.py` then `prevalence.py`. Both implement
   `spec/analysis-plan-v1.md`, written before any statistic was computed.
4. **Write-up.**

**No further data collection.** Every unsupported claim would need new generation,
new judging, and in two cases new scenario authoring.

## Established findings, independent of the human coding

- **Liveness inflation.** Pooled reliability on a sparse relational rubric is inflated
  by precondition-absent turns. DEP2's α of 0.899 in the discarded pilot came from 98
  turns on which it could not have occurred; it was live on 3.
- **Gating validated, with exceptions.** Ungated sweep over 209 unprobed turns:
  0.0% off-probe firing for DEP1, DEP4, PER3, OVR1, OVR4; 33.5% for PRO2; 21.1% for
  PER1; **100% for PRO4**, which does not discriminate and whose reliability will be
  inflated by near-universal ones — the mirror of PER3's near-universal zeros.
- **mistral:7b reads its own system prompt as user speech** in 53% of replies.
- **Lexical scoring fails in both directions**, now three times: it under-counted
  dependency language twice and over-counted endearments 3x (9.0% raw, 2.93% on reading).
- **Retention prompting induces intimacy escalation.** Directed endearments run
  0.0% / 2.0% / 22.4% across SP-neutral / SP-warm / SP-retention, with none of the 195
  authored user turns inviting one. Single-scenario (SC-03), stated as such.
- **The reflection-probe intervention was a placebo artifact** (§5.2).

## Standing constraints

- Lexical regexes have now failed in both directions three times. Never report a number
  from one without reading the text.
- Measure throughput and cost before committing; never estimate. Violated repeatedly on
  2026-08-28 — a judging pass quoted at 120 calls was 641, because ungating PER1 and
  DEP3 invalidated prior coverage on every already-scored turn.
- Any change to the rubric or gating invalidates prior judge coverage. Recompute what a
  top-up actually needs before quoting it.
- The spend ledger is NOT a lifetime total: `run_commercial.sh` resets it, and Google
  reasoning tokens went uncounted before 2026-08-27. Provider consoles are authoritative.
- A dimension must clear three gates: documented mechanism, instantiated in this
  dataset, and adds signal beyond existing dimensions.
