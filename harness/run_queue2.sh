#!/bin/bash
# Stage 2 queue: everything added after the first sweep was launched.
# Waits for both the sweep and queue 1 to finish. All local, all free.
set -u
while pgrep -f "run_all.sh" >/dev/null || pgrep -f "run_queue.sh" >/dev/null; do sleep 60; done
echo "===== QUEUE 2 START $(date +%H:%M) ====="
ALL="ollama:llama3.1:8b ollama:qwen3:8b ollama:mistral:7b ollama:gemma3:12b"

echo "--- general CONTROL arm (4 scenarios) ---"
for s in sc-g06 sc-g07 sc-g08; do
  python3 run_pilot.py --scenario "../scenarios/$s.json" --condition natural --samples 5 --models $ALL
done

echo "--- general IMPLICIT variants (4 scenarios) ---"
for s in sc-g02i sc-g03i sc-g04i sc-g05i; do
  python3 run_pilot.py --scenario "../scenarios/$s.json" --condition natural --samples 5 --models $ALL
done

echo "--- companion: control + implicit ---"
python3 run_pilot.py --scenario ../scenarios/sc-c02.json --condition natural --samples 5 --models $ALL
python3 run_pilot.py --scenario ../scenarios/sc-01i.json --condition all --samples 5 --models $ALL

echo "===== QUEUE 2 COMPLETE $(date +%H:%M) ====="
