#!/bin/bash
# Runs after the current sweep exits. All local, all free.
set -u
while pgrep -f "run_all.sh" >/dev/null; do sleep 60; done
echo "===== QUEUE START $(date +%H:%M) ====="
ALL="ollama:llama3.1:8b ollama:qwen3:8b ollama:mistral:7b ollama:gemma3:12b"

echo "--- [1/3] SC-03 on the two missing families ---"
python3 run_pilot.py --scenario ../scenarios/sc-03.json --condition natural --samples 5 \
    --models ollama:mistral:7b ollama:gemma3:12b

echo "--- [2/3] SC-01 retest: powers the rejected hypotheses (sec 5) ---"
python3 run_pilot.py --scenario ../scenarios/sc-01.json --condition all --samples 5 --models $ALL

echo "--- [3/3] System-prompt experiment: neutral vs retention ---"
python3 run_pilot.py --scenario ../scenarios/sc-03.json --condition natural --samples 5 \
    --system-prompt neutral --models $ALL
python3 run_pilot.py --scenario ../scenarios/sc-03.json --condition natural --samples 5 \
    --system-prompt retention --models $ALL

echo "===== QUEUE COMPLETE $(date +%H:%M) ====="
