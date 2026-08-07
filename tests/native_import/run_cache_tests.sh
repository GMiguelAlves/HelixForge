#!/usr/bin/env bash

set -euo pipefail

project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
nextflow_bin=${NEXTFLOW_BIN:-nextflow}
source_fixture="${project_root}/tests/fixtures/native_import"
case_root="${project_root}/results/test/native-import-cache"
fixture_root="${case_root}/fixtures"
work_root="${case_root}/work"

case "$case_root" in
    "${project_root}"/results/test/*) ;;
    *) echo "Unsafe test path: $case_root" >&2; exit 2 ;;
esac
rm -rf "$case_root"
mkdir -p "$case_root"
cp -R "$source_fixture" "$fixture_root"

run_case() {
    local provider=$1
    local trace=$2
    local target=$3
    shift 3
    "$nextflow_bin" run "${project_root}/tests/native_import/main.nf" \
        -c "${project_root}/tests/native_import/nextflow.config" \
        -profile local -stub-run -resume -ansi-log false \
        -work-dir "$work_root" \
        --provider "$provider" \
        --fixture_root "$fixture_root" \
        --target_root "$target" \
        --outdir "${case_root}/nextflow-${provider}" \
        --trace_file "$trace" "$@"
}

assert_trace() {
    local trace=$1
    local pattern=$2
    local status=$3
    local minimum=${4:-1}
    python3 - "$trace" "$pattern" "$status" "$minimum" <<'PY'
import csv
import re
import sys

trace, pattern, status, minimum = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
with open(trace, newline="", encoding="utf-8") as handle:
    rows = list(csv.DictReader(handle, delimiter="\t"))
matches = [row for row in rows if re.search(pattern, row["name"]) and row["status"] == status]
if len(matches) < minimum:
    observed = [(row.get("name"), row.get("status")) for row in rows]
    raise SystemExit(
        f"Expected >= {minimum} trace rows matching {pattern!r}/{status}; observed {observed}"
    )
PY
}

assert_all_cached() {
    local trace=$1
    python3 - "$trace" <<'PY'
import csv
import sys

with open(sys.argv[1], newline="", encoding="utf-8") as handle:
    rows = list(csv.DictReader(handle, delimiter="\t"))
bad = [(row.get("name"), row.get("status")) for row in rows if row.get("status") != "CACHED"]
if bad:
    raise SystemExit(f"Expected every resumed task to be CACHED; observed {bad}")
PY
}

run_case star "${case_root}/star_initial.tsv" "${case_root}/star_outputs"
run_case star "${case_root}/star_resume.tsv" "${case_root}/star_outputs"
assert_all_cached "${case_root}/star_resume.tsv"

run_case star "${case_root}/star_parameter.tsv" "${case_root}/star_outputs" --star_count_column stranded_forward
assert_trace "${case_root}/star_parameter.tsv" 'IMPORT_SOURCE' CACHED 2
assert_trace "${case_root}/star_parameter.tsv" 'STAR_(SAMPLE_TABLE|IMPORT)' COMPLETED 2

printf ' \n' >> "${fixture_root}/star/sample_a/manifest.json"
run_case star "${case_root}/star_manifest.tsv" "${case_root}/star_outputs" --star_count_column stranded_forward
assert_trace "${case_root}/star_manifest.tsv" 'IMPORT_SOURCE' COMPLETED 1
assert_trace "${case_root}/star_manifest.tsv" 'STAR_IMPORT' COMPLETED 1

run_case salmon "${case_root}/salmon_initial.tsv" "${case_root}/salmon_outputs"
run_case salmon "${case_root}/salmon_resume.tsv" "${case_root}/salmon_outputs"
assert_all_cached "${case_root}/salmon_resume.tsv"

printf 'chr1\ttest\ttranscript\t201\t250\t.\t+\t.\tgene_id "gene:gene_c.1"; transcript_id "transcript:tx_c.1";\n' \
    >> "${fixture_root}/annotation.gtf"
run_case salmon "${case_root}/salmon_annotation.tsv" "${case_root}/salmon_outputs"
assert_trace "${case_root}/salmon_annotation.tsv" 'TX2GENE_BUILD' COMPLETED 1
assert_trace "${case_root}/salmon_annotation.tsv" 'SALMON_IMPORT' COMPLETED 1
assert_trace "${case_root}/salmon_annotation.tsv" 'IMPORT_SOURCE' CACHED 2

echo '[OK] Import cache reuse and parameter, manifest, and annotation invalidation validated.'
