#!/bin/bash

# Master script to generate Diptera ALG plots from BUSCO results.
# Run from a project directory containing BUSCO outputs. The accession table can
# be supplied with ACCESSION_FILE or discovered beside this script.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_ROOT="${DATA_ROOT:-.}"
BUSCO_DIR="${BUSCO_DIR:-${DATA_ROOT}/busco}"
OUTPUT_DIR="${OUTPUT_DIR:-${DATA_ROOT}/diptera_algs}"
ALG_REF="${ALG_REF:-}"
LINEAGE="${LINEAGE:-auto}"
TOLID_FILE="${TOLID_FILE:-}"
LABEL_WINDOW_MB="${LABEL_WINDOW_MB:-0}"
LABEL_WINDOW_MIN_BUSCOS="${LABEL_WINDOW_MIN_BUSCOS:-5}"
LABEL_WINDOW_MIN_FRACTION="${LABEL_WINDOW_MIN_FRACTION:-0.5}"

ACCESSION_TABLE_CANDIDATES=(
  "tolid_accessions.tsv"
  "tolid_accession.tsv"
  "tolids_accession.tsv"
  "tolids_accessions.tsv"
  "${SCRIPT_DIR}/tolid_accessions.tsv"
  "${SCRIPT_DIR}/tolid_accession.tsv"
  "${SCRIPT_DIR}/tolids_accession.tsv"
  "${SCRIPT_DIR}/tolids_accessions.tsv"
)

if command -v diptera-busco-painter >/dev/null 2>&1; then
  RUN_CMD=(diptera-busco-painter run)
else
  export PYTHONPATH="${SCRIPT_DIR}/src${PYTHONPATH:+:${PYTHONPATH}}"
  RUN_CMD=(python3 -m diptera_busco_painter run)
fi

resolve_accession_file() {
  if [[ -n "${ACCESSION_FILE:-}" ]]; then
    printf '%s\n' "$ACCESSION_FILE"
    return 0
  fi

  local candidate
  for candidate in "${ACCESSION_TABLE_CANDIDATES[@]}"; do
    if [[ -f "$candidate" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

ACCESSION_FILE="$(resolve_accession_file)" || {
  echo "ERROR: no accession table found. Set ACCESSION_FILE or add tolid_accessions.tsv in $(pwd) or ${SCRIPT_DIR}"
  exit 1
}

TOLID_SOURCE=""
TOLID_SOURCE_MODE="list"
if [[ -n "$TOLID_FILE" ]]; then
  if [[ ! -f "$TOLID_FILE" ]]; then
    echo "ERROR: TOLID_FILE not found: $TOLID_FILE"
    exit 1
  fi
  TOLID_SOURCE="$TOLID_FILE"
else
  TOLID_SOURCE="$ACCESSION_FILE"
  TOLID_SOURCE_MODE="accession"
fi

if [[ -n "$ALG_REF" && ! -f "$ALG_REF" ]]; then
  echo "ERROR: custom ALG reference table not found: $ALG_REF"
  exit 1
fi

mkdir -p "$OUTPUT_DIR" || {
  echo "ERROR: could not create output directory: $OUTPUT_DIR"
  exit 1
}

get_accession() {
  local tolid="$1"
  awk -F '\t' -v tolid="$tolid" '$1 == tolid {print $2; exit}' "$ACCESSION_FILE"
}

is_header_tolid() {
  local tolid="$1"
  local lower
  lower="$(printf '%s' "$tolid" | tr '[:upper:]' '[:lower:]')"
  [[ "$lower" == "tolid" || "$lower" == "tol_id" || "$lower" == "sample" ]]
}

run_args() {
  local busco_input="$1"
  local output_dir="$2"
  local accession="$3"

  printf '%s\0' \
    --query_table "$busco_input" \
    --prefix "${output_dir}/" \
    --lineage "$LINEAGE" \
    --accession "$accession" \
    --write-summary \
    --label-threshold 5 \
    --label-window-mb "$LABEL_WINDOW_MB" \
    --label-window-min-buscos "$LABEL_WINDOW_MIN_BUSCOS" \
    --label-window-min-fraction "$LABEL_WINDOW_MIN_FRACTION"
  if [[ -n "$ALG_REF" ]]; then
    printf '%s\0' --reference_table "$ALG_REF"
  fi
}

process_tolid() {
  local tolid="$1"
  local accession busco_input tolid_output

  echo "================================"
  echo "Processing: $tolid"
  echo "================================"

  accession="$(get_accession "$tolid")"
  if [[ -z "$accession" ]]; then
    echo "WARN: No accession found for $tolid in $ACCESSION_FILE. Skipping."
    return 2
  fi

  echo "Accession: $accession"

  busco_input="${BUSCO_DIR}/${tolid}/full_table.tsv"
  if [[ ! -f "$busco_input" ]]; then
    echo "WARN: Missing BUSCO file: $busco_input. Skipping."
    return 2
  fi

  tolid_output="${OUTPUT_DIR}/${tolid}"
  mkdir -p "$tolid_output" || {
    echo "ERROR: Could not create output directory: $tolid_output"
    return 1
  }

  echo "Running Diptera BUSCO painter..."
  local -a args=()
  while IFS= read -r -d '' arg; do
    args+=("$arg")
  done < <(run_args "$busco_input" "$tolid_output" "$accession")

  rm -f "${tolid_output}/${tolid}.png" "${tolid_output}/${tolid}.svg"
  if ! "${RUN_CMD[@]}" "${args[@]}"; then
    echo "ERROR: Diptera BUSCO painter failed for $tolid"
    return 1
  fi

  echo "Finished: $tolid"
  echo ""
  return 0
}

total=0
success=0
failed=0
skipped=0

if [[ "$TOLID_SOURCE_MODE" == "accession" ]]; then
  echo "ToLID source: first column of $TOLID_SOURCE"
else
  echo "ToLID source: $TOLID_SOURCE"
fi
echo "Accession table: $ACCESSION_FILE"
if [[ "$LINEAGE" == "auto" ]]; then
  echo "Lineage mode: auto (NCBI taxid lookup from assembly accession)"
else
  echo "Lineage mode: $LINEAGE"
fi

while IFS= read -r line || [[ -n "$line" ]]; do
  if [[ "$TOLID_SOURCE_MODE" == "accession" ]]; then
    tolid="${line%%$'\t'*}"
  else
    tolid="$line"
  fi

  [[ -z "$tolid" ]] && continue
  [[ "$tolid" =~ ^# ]] && continue
  is_header_tolid "$tolid" && continue

  total=$((total + 1))
  process_tolid "$tolid"
  status=$?

  if [[ $status -eq 0 ]]; then
    success=$((success + 1))
  elif [[ $status -eq 2 ]]; then
    skipped=$((skipped + 1))
  else
    failed=$((failed + 1))
  fi
done < "$TOLID_SOURCE"

echo "================================"
echo "Batch complete"
echo "   Total:   $total"
echo "   Success: $success"
echo "   Skipped: $skipped"
echo "   Failed:  $failed"
echo "   Output:  $OUTPUT_DIR"
echo "================================"
