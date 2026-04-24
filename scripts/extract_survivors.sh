#!/usr/bin/env bash
# Dump all surviving mutants to mutmut_survivors.txt for manual grouping.
# Handles both comma-separated IDs ("1, 5, 9") and ranges ("45-100").
set +e
cd "$(dirname "$0")/.."
OUT=docs/baselines/2026-04-24/mutmut_survivors.txt
export PATH="$(pwd)/.venv/Scripts:$PATH"

RESULTS_FILE=docs/baselines/2026-04-24/mutmut_results.txt
if [ ! -f "$RESULTS_FILE" ]; then
    echo "ERROR: $RESULTS_FILE not found — run mutmut first" >&2
    exit 1
fi

# Pull everything between "Survived" and the next blank line or next top-level section.
# Expand "N-M" ranges into individual IDs. Concatenate all per-file sections.
ids=$(awk '
    /^Survived/        { in_survived=1; next }
    in_survived && /^[A-Za-z]/ && !/^----/ { in_survived=0 }
    in_survived        { print }
' "$RESULTS_FILE" \
  | tr ',' '\n' \
  | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' \
  | awk '
      /^[0-9]+$/               { print $0; next }
      /^[0-9]+-[0-9]+$/        { split($0,a,"-"); for (i=a[1]; i<=a[2]; i++) print i; next }
  ')

count=$(echo "$ids" | grep -c '^[0-9]')
if [ "$count" -eq 0 ]; then
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
