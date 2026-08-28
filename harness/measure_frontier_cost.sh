#!/bin/bash
# Measure before committing. Gemini 3.x reasons by DEFAULT and bills those tokens as
# output; run_pilot.py does not disable it, so the cost estimate taken from Haiku's
# output profile may be several times too low for the Pro model. Run ONE scenario per
# model, read the real spend, then extrapolate to fifteen.
set -u
BUDGET=${1:-2.00}
CAP=$(python3 -c "
import json,pathlib
p=pathlib.Path('../runs/.spend_ledger.json')
print(f\"{(json.loads(p.read_text())['usd'] if p.exists() else 0)+$BUDGET:.4f}\")")
BEFORE=$(python3 -c "
import json,pathlib
p=pathlib.Path('../runs/.spend_ledger.json')
print(json.loads(p.read_text())['usd'] if p.exists() else 0)")
echo "one scenario, both frontier models, cap \$$CAP"
python3 run_pilot.py --scenario ../scenarios/sc-g04.json --condition natural --samples 5 \
    --models google:gemini-3.1-pro-preview anthropic:claude-sonnet-5 --max-spend $CAP
python3 - "$BEFORE" <<'EXTRAP'
import json, pathlib, sys
before = float(sys.argv[1])
now = json.loads((pathlib.Path("..")/"runs"/".spend_ledger.json").read_text())["usd"]
spent = now - before
print(f"\n===== MEASURED =====")
print(f"  1 scenario, 2 models, n=5 : ${spent:.4f}")
print(f"  extrapolated to 15        : ${spent*15:.2f}")
print(f"  (that is BOTH models combined; roughly 40/60 Google/Anthropic by list price)")
print(f"\n  -> budget for run_frontier.sh: ${spent*15*1.25:.2f} with 25% headroom")
EXTRAP
