#!/bin/bash
# Full local sweep: 4 general-profile scenarios x 4 open model families, n=5, natural.
# Free (all local). Saves incrementally -- a crash loses at most one sample.
set -u
M="ollama:llama3.1:8b ollama:qwen3:8b ollama:mistral:7b ollama:gemma3:12b"
for s in sc-g02 sc-g03 sc-g04 sc-g05; do
  echo "===== $s  $(date +%H:%M:%S) ====="
  python3 run_pilot.py --scenario "../scenarios/$s.json" \
      --condition natural --samples 5 --models $M
done
echo "===== SWEEP COMPLETE $(date +%H:%M:%S) ====="
