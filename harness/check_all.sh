#!/bin/sh
# Every check, in order. Non-zero exit means the manuscript and the repository
# disagree about something. Run before any push or submission.
#
# An earlier version of this script piped each check to `tail -1`, which discards
# the check's exit status: it printed ALL CHECKS PASS while check_citations was
# failing. Exit codes are now captured explicitly.
cd "$(dirname "$0")" || exit 2
# PYTHON=../.venv/bin/python ./check_all.sh to pin the interpreter.
PY=${PYTHON:-python3}
status=0

run() {
    name=$1; shift
    out=$("$@" 2>&1); rc=$?
    echo "$out" | tail -1
    if [ $rc -ne 0 ]; then
        echo "  ^ $name FAILED (exit $rc)"
        echo "$out" | grep -E "^(FAIL|UNFETCHED)" | sed 's/^/    /'
        status=1
    fi
}

"$PY" figures.py --save > /dev/null || { echo "figures.py FAILED"; exit 2; }
"$PY" sync_tables.py || status=1
run "check_manuscript" "$PY" check_manuscript.py
run "check_claims"     "$PY" check_claims.py
run "check_citations"  "$PY" check_citations.py

if [ $status -eq 0 ]; then
    echo "ALL CHECKS PASS"
else
    echo "CHECKS FAILED"
fi
exit $status
