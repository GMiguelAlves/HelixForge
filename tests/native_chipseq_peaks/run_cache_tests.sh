#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TEST_ROOT="${ROOT}/tests/native_chipseq_peaks"
NEXTFLOW_BIN="${NEXTFLOW_BIN:-nextflow}"
if ! command -v macs3 >/dev/null 2>&1; then
    echo "SKIP: MACS3 3.0.4 is not installed in the active test environment" >&2
    exit 77
fi

run_case() {
    local name="$1"; shift
    "${NEXTFLOW_BIN}" run "${TEST_ROOT}/main.nf" -c "${TEST_ROOT}/nextflow.config" -resume -ansi-log false "$@" 2>&1 | tee "${TEST_ROOT}/${name}.log"
}

python3 "${TEST_ROOT}/generate_fixture.py" --outdir "${TEST_ROOT}/fixture_work"
run_case baseline
run_case resume
[[ "$(grep -c 'Cached process.*MACS3_CALLPEAK' "${TEST_ROOT}/resume.log")" -eq 2 ]]

run_case q_changed --q_value 0.2
[[ "$(grep -c 'Submitted process.*MACS3_CALLPEAK' "${TEST_ROOT}/q_changed.log")" -eq 2 ]]
run_case baseline_restored --q_value 0.5

python3 "${TEST_ROOT}/generate_fixture.py" --outdir "${TEST_ROOT}/fixture_work" --treatment-extra 1
run_case treatment_changed --q_value 0.5
grep -q 'Submitted process.*MACS3_CALLPEAK (chip_rep1' "${TEST_ROOT}/treatment_changed.log"
grep -q 'Cached process.*MACS3_CALLPEAK (chip_rep2' "${TEST_ROOT}/treatment_changed.log"

python3 "${TEST_ROOT}/generate_fixture.py" --outdir "${TEST_ROOT}/fixture_work" --control-extra 1
run_case control_changed --q_value 0.5
[[ "$(grep -c 'Submitted process.*MACS3_CALLPEAK' "${TEST_ROOT}/control_changed.log")" -eq 2 ]]

run_case peak_type_changed --q_value 0.5 --peak_type broad
[[ "$(grep -c 'Submitted process.*MACS3_CALLPEAK' "${TEST_ROOT}/peak_type_changed.log")" -eq 2 ]]
echo "PASS: resume and q-value, peak type, treatment BAM and control BAM invalidation"
