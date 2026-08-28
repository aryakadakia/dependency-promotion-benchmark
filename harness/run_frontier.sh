#!/bin/bash
# Frontier commercial arm: adds a Pro-tier model from each vendor, so the commercial
# side becomes 2 vendors x 2 capability tiers instead of two small models.
#
#   Google    gemini-3.7-flash (have)  +  gemini-3.1-pro-preview (this run)
#   Anthropic claude-haiku-4-5 (have)  +  claude-sonnet-5        (this run)
#
# Measured cost from claude-haiku's own 15-scenario x n=5 run: 1.27M input tokens,
# 201k output. At list prices that is $4.95 Google and $6.82 Anthropic.
#
# BUDGET is what this run may add ON TOP of the existing ledger, so historical spend
# is never discarded to run a script -- the trap that aborted the dropout diagnostic.
set -u
BUDGET=${1:-16.00}

CAP=$(python3 -c "
import json,pathlib
p=pathlib.Path('../runs/.spend_ledger.json')
prior=json.loads(p.read_text())['usd'] if p.exists() else 0.0
print(f'{prior + $BUDGET:.4f}')
")
echo "===== FRONTIER ARM  $(date +%H:%M) ====="
echo "  ledger + \$$BUDGET  ->  cumulative cap \$$CAP"

M="google:gemini-3.1-pro-preview anthropic:claude-sonnet-5"

# One real call per model before committing to 30 scenario-runs. claude-sonnet-5 has
# never been exercised by this harness and takes a different thinking parameter shape
# from haiku; a wrong parameter would otherwise fail every call after the money is
# already committed.
echo "--- smoke test ---"
python3 - <<'SMOKE' || { echo "SMOKE FAILED — aborting before spending"; exit 1; }
import sys, providers
for m in ("google:gemini-3.1-pro-preview", "anthropic:claude-sonnet-5"):
    ok, why = providers.check(m)
    if not ok:
        print(f"  {m}: {why}"); sys.exit(1)
    if not providers.pricing_for(m):
        print(f"  {m}: UNPRICED — the spend cap would not apply. Aborting.")
        sys.exit(1)
    try:
        r = providers.chat(m, "You are a companion.",
                           [{"role":"user","content":"say ok"}], max_tokens=256)
        print(f"  OK  {m:<32} {r.input_tokens}in/{r.output_tokens}out  {r.text.strip()[:32]!r}")
    except Exception as e:
        print(f"  FAIL {m}: {type(e).__name__}: {str(e)[:200]}"); sys.exit(1)
SMOKE
echo "  both reachable and priced — proceeding"

for s in ../scenarios/*.json; do
  echo "--- $(basename $s .json)  $(date +%H:%M) ---"
  python3 run_pilot.py --scenario "$s" --condition natural --samples 5 \
      --models $M --max-spend $CAP || { echo "STOPPED (cap or error)"; break; }
done

python3 -c "
import json,pathlib
p=pathlib.Path('../runs/.spend_ledger.json')
print(f\"===== FRONTIER COMPLETE  ledger now \${json.loads(p.read_text())['usd']:.4f} =====\")
"
