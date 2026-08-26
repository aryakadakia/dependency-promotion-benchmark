# Where this is up to

_Updated 2026-08-26. Update this file whenever the plan changes._

## Running now (unattended, free, local)

Three chained stages. Each waits for the previous. Nothing needs supervision;
every run saves incrementally, so a sleeping laptop loses at most one sample.

| Stage | Contents |
|---|---|
| sweep (`run_all.sh`) | SC-G02–G05 explicit × 4 local models × n=5 |
| queue 1 (`run_queue.sh`) | SC-03 on mistral+gemma3 · SC-01 retest (natural/probe/placebo) · system-prompt experiment (neutral vs retention) |
| queue 2 (`run_queue2.sh`) | general control ×3 · general implicit ×4 · companion control · companion implicit |

Check progress:
```bash
cd harness && python3 -c "
import json,glob
for f in sorted(glob.glob('../runs/SC-*n5*.json')):
    d=json.load(open(f)); n=sum(len([s for s in c.get('samples',[]) if isinstance(s,list)]) for cc in d['results'].values() for c in cc.values())
    print(f\"{d['scenario_id']:<10}{n}\")"
```

## Then, in order

**1. Commercial runs (~\$3, about an hour).** Deliberately BEFORE hand-coding, so the
coding pool spans the full capability range and you only code once. Judge validity
established on 8B outputs may not transfer to frontier outputs.

```bash
export GOOGLE_API_KEY=...   # ANTHROPIC_API_KEY too
cd harness
for s in ../scenarios/*.json; do
  python3 run_pilot.py --scenario "$s" --condition natural --samples 5 \
    --models google:gemini-3.7-flash anthropic:claude-haiku-4-5 --max-spend 8.00
done
```
Estimated: gemini-3.7-flash ~\$1.20, claude-haiku-4-5 ~\$1.60 for all 15 scenarios.
The `--max-spend` cap tracks real token usage and aborts mid-run if exceeded.

**2. Judging (free, local, overnight).**
```bash
cd harness && python3 judge.py "../runs/*.json"
```
Three judges from different families, blind to model and condition, no self-scoring.
`--min-samples 5` excludes n=1 pilot runs by default.

**3. Hand-coding (yours, 1–2 hours).**
```bash
cd harness && python3 handcode.py --n 100
```
Resumable; `q` saves and quits. Then regenerate the second-coder packet:
```bash
python3 make_coder_packet.py --n 35     # email paper/coder_packet.xlsx
```
Same seed as your pool, so the second coder scores the SAME items — required for
human–human α. `runs/coder_packet_key.json` stays local, never emailed.

**4. Analysis.**
```bash
python3 alpha.py --human ../runs/handcoded.json --human2 <second coder>
python3 analyze.py --by-scenario --by-pathway
```
Read `alpha.py` output first. Dimensions below α 0.667 are reported as unreliable,
not dropped — means from those look precise and are not.

## Open items

- **Second coder** — ask a labmate for the 35-item packet. Moves the limitation from
  "single coder" to "two coders, α reported."
- **Abstract, Results, Discussion, Limitations** in `paper/manuscript.md` are placeholders.
- **Remote repo** not created. Local commits only — that's a deliberate choice, not an oversight.

## Standing constraints

- Difficulty comes from realism (system prompt, duration, base rates), never contrivance.
- Never call an API cost "free" without verifying the project has no billing attached.
- Single-sample results are observations, not findings.
- Verify negative literature claims with academic-domain-restricted search before writing them.
