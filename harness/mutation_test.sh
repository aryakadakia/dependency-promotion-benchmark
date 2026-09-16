#!/bin/sh
# Mutation test: plant a known error in the manuscript, confirm check_all.sh
# catches it, restore. A suite of assertions that never fails is worthless, and
# the first run of this found four planted errors going undetected: the number
# checker proves a figure is sourced SOMEWHERE, not that it is in the right
# sentence. Those now have binding assertions in check_claims.py.
#
# Restores with `git checkout`, not a /tmp copy. An earlier version restored from
# a stale backup and left a planted value in the manuscript.
#
# Run after adding any assertion, to confirm the assertion can actually fail.
cd "$(dirname "$0")/.." || exit 2
MS=paper/manuscript.md

if ! git diff --quiet -- $MS; then
    echo "REFUSING: $MS has uncommitted changes; commit or stash first."
    exit 2
fi
trap 'git checkout -- $MS' EXIT INT TERM

pass=0; fail=0; skip=0
mutate() {
    desc=$1; from=$2; to=$3
    git checkout -- $MS
    python3 - "$from" "$to" <<'PY'
import sys, pathlib
p = pathlib.Path("paper/manuscript.md"); s = p.read_text()
if sys.argv[1] not in s:
    sys.exit(3)
p.write_text(s.replace(sys.argv[1], sys.argv[2], 1))
PY
    if [ $? -eq 3 ]; then echo "SKIP    $desc (string not found)"; skip=$((skip+1)); return; fi
    if ./harness/check_all.sh >/dev/null 2>&1; then
        echo "MISSED  $desc"; fail=$((fail+1))
    else
        echo "caught  $desc"; pass=$((pass+1))
    fi
}

mutate "disagreement total"      "Of 39 disagreements"          "Of 41 disagreements"
mutate "one-directional count"   "threshold, 33 are cases"      "threshold, 35 are cases"
mutate "off-probe overall rate"  "Overall firing was 14.7%"     "Overall firing was 15.7%"
mutate "provenance proportion"   "82% of DEP1"                  "85% of DEP1"
mutate "contested dimension set" "(DEP1, DEP2, DEP6, DEP7, PER1, PER3)" "(DEP1, DEP2, DEP6, DEP7, PER1, PRO2)"
mutate "stimulus count"          "(PER3 on two, OVR3 on three"  "(PER3 on four, OVR3 on three"
mutate "judge AC1 in 5.5"        "(DEP4, 0.848)"                "(DEP4, 0.898)"
mutate "frame composition"       "385 \`warm\` turns"           "395 \`warm\` turns"
mutate "off-gate judgement count" "120 of the 397"              "120 of the 407"
mutate "decision-rule count"     "Five dimensions"              "Four dimensions"
mutate "inherited liveness"      "OVR1 (68 frame turns)"        "OVR1 (86 frame turns)"

git checkout -- $MS
if ./harness/check_all.sh >/dev/null 2>&1; then
    echo "restored clean"
else
    echo "RESTORE PROBLEM"; fail=$((fail+1))
fi
echo "caught=$pass missed=$fail skipped=$skip"
exit $fail
