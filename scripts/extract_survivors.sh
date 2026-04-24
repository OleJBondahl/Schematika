#!/usr/bin/env bash
# Dump up to 20 surviving mutants to mutmut_survivors.txt for manual grouping.
set +e
cd "$(dirname "$0")/.."
OUT=docs/baselines/2026-04-24/mutmut_survivors.txt
export PATH="$(pwd)/.venv/Scripts:$PATH"

# mutmut 2.x uses `results` to list + `show <id>` per mutant.
# Grab survivors from results — they appear under a 'Survived' section.
RESULTS_FILE=docs/baselines/2026-04-24/mutmut_results.txt
if [ ! -f "$RESULTS_FILE" ]; then
    echo "ERROR: $RESULTS_FILE not found — run mutmut first" >&2
    exit 1
fi

# Extract survivor IDs: lines under "Survived" header, usually comma-separated integers
ids=$(awk '/^Survived/{flag=1;next} /^[A-Z]/{flag=0} flag{print}' "$RESULTS_FILE" \
      | tr -d ' \r\n' | tr ',' '\n' | grep -E '^[0-9]+$' | head -20)

if [ -z "$ids" ]; then
    echo "No survivors found in $RESULTS_FILE" > "$OUT"
    exit 0
fi

: > "$OUT"
n=0
for id in $ids; do
    echo "=== Mutant $id ===" >> "$OUT"
    .venv/Scripts/mutmut.exe show "$id" >> "$OUT" 2>&1
    echo "" >> "$OUT"
    n=$((n+1))
done
echo "Extracted $n survivors to $OUT"
