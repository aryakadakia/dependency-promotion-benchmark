#!/bin/sh
# Every check, in order. Non-zero exit means the manuscript and the repository
# disagree about something. Run before any push or submission.
set -e
cd "$(dirname "$0")"
python3 figures.py --save > /dev/null
python3 sync_tables.py
python3 check_manuscript.py | tail -1
python3 check_claims.py     | tail -1
python3 check_citations.py  | tail -1
echo "ALL CHECKS PASS"
