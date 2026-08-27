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
