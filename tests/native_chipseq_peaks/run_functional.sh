#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TEST_ROOT="${ROOT}/tests/native_chipseq_peaks"
NEXTFLOW_BIN="${NEXTFLOW_BIN:-nextflow}"
NEXTFLOW_JAR="${NEXTFLOW_JAR:-}"
MACS3_IMAGE="${MACS3_TEST_IMAGE:-quay.io/biocontainers/macs3:3.0.4--py312h71493bf_0}"

run_nextflow() {
    if [[ -n "$NEXTFLOW_JAR" ]]; then
        java -jar "$NEXTFLOW_JAR" "$@"
    else
        "$NEXTFLOW_BIN" "$@"
    fi
}

if ! docker image inspect "$MACS3_IMAGE" >/dev/null 2>&1; then
    echo "SKIP: MACS3 image is not available: $MACS3_IMAGE" >&2
    exit 77
fi
python3 "${TEST_ROOT}/generate_fixture.py" --outdir "${TEST_ROOT}/fixture_work"
rm -rf "${TEST_ROOT}/results"

run_nextflow run "${TEST_ROOT}/main.nf" -c "${TEST_ROOT}/nextflow.config" -ansi-log false \
    --macs3_container "$MACS3_IMAGE"
python3 - "${TEST_ROOT}/results" <<'PY'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1]) / "peaks"
manifests = sorted(root.glob("**/*.peak_calling/manifest.json"))
assert len(manifests) == 2, manifests
ids = set()
for path in manifests:
    document = json.loads(path.read_text())
    assert document["metrics"]["total_peaks"] > 0, document
    assert document["peak_type"] == "narrow"
    peak = path.parent / "peaks.narrowPeak"
    for line in peak.read_text().splitlines():
        columns = line.split("\t")
        assert len(columns) == 10
        assert int(columns[1]) >= 0 and int(columns[2]) > int(columns[1])
    assert document["control_record_id"] == "input_rep1"
    ids.add(document["record_id"])
assert ids == {"chip_rep1", "chip_rep2"}, ids
PY

run_nextflow run "${TEST_ROOT}/main.nf" -c "${TEST_ROOT}/nextflow.config" -resume -ansi-log false \
    --macs3_container "$MACS3_IMAGE" 2>&1 | tee "${TEST_ROOT}/resume.log"
grep -q 'Cached process.*MACS3_CALLPEAK' "${TEST_ROOT}/resume.log"
grep -q 'Cached process.*PEAK_CALLING_AGGREGATE' "${TEST_ROOT}/resume.log"
echo "PASS: MACS3 functional, independent replicates, formats, metadata and resume"
