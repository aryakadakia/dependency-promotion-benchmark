#!/bin/bash
# Commercial arm. Waits for local runs, then all 15 scenarios on two vendors.
# CUMULATIVE spend cap across every invocation -- see providers.set_spend_cap.
set -u
CAP=4.50   # USD, total across ALL scenarios and both providers

while pgrep -f "run_queue2.sh" >/dev/null || pgrep -f "run_pilot.py" >/dev/null; do
  sleep 60
done
echo "===== COMMERCIAL START $(date +%H:%M)  cap \$$CAP total ====="
python3 -c "import providers; providers.reset_spend_ledger(); print('  ledger reset')"

# One real call per vendor before committing to 15 scenarios. The Anthropic path
# has never been exercised -- a wrong parameter would otherwise fail every call.
echo "--- smoke test: one call per vendor ---"
python3 - <<'SMOKE' || { echo "SMOKE TEST FAILED — aborting before the real run"; exit 1; }
import sys, providers
for m in ("google:gemini-3.7-flash", "anthropic:claude-haiku-4-5"):
    ok, why = providers.check(m)
    if not ok:
        print(f"  {m}: {why}"); sys.exit(1)
    try:
        r = providers.chat(m, "You are a companion.",
                           [{"role": "user", "content": "say ok"}], max_tokens=64)
        print(f"  OK  {m:<32} {r.input_tokens}in/{r.output_tokens}out  {r.text.strip()[:40]!r}")
    except Exception as e:
        print(f"  FAIL {m}: {type(e).__name__}: {str(e)[:180]}"); sys.exit(1)
SMOKE
echo "  both vendors reachable — proceeding"

M="google:gemini-3.7-flash anthropic:claude-haiku-4-5"

for s in ../scenarios/*.json; do
  echo "--- $(basename $s .json) ---"
  python3 run_pilot.py --scenario "$s" --condition natural --samples 5 \
      --models $M --max-spend $CAP || { echo "STOPPED (cap or error)"; break; }
done

echo "--- system-prompt arm on commercial models ---"
for sp in neutral retention; do
  python3 run_pilot.py --scenario ../scenarios/sc-03.json --condition natural --samples 5 \
      --system-prompt $sp --models $M --max-spend $CAP || break
done

python3 -c "
import json,pathlib
p=pathlib.Path('../runs/.spend_ledger.json')
print(f\"===== COMMERCIAL COMPLETE  total spend \${json.loads(p.read_text())['usd']:.4f} =====\" if p.exists() else 'no spend recorded')
"
