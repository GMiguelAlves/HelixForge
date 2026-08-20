#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TEST_ROOT="${ROOT}/tests/native_chipseq_peak_annotation"
python3 "${TEST_ROOT}/generate_fixture.py" --outdir "${TEST_ROOT}/fixture_work"
"${NEXTFLOW_BIN:-nextflow}" run "${TEST_ROOT}/main.nf" -c "${TEST_ROOT}/nextflow.config" -stub-run -ansi-log false
"${NEXTFLOW_BIN:-nextflow}" run "${TEST_ROOT}/main.nf" -c "${TEST_ROOT}/nextflow.config" -stub-run -resume -ansi-log false
"${NEXTFLOW_BIN:-nextflow}" run "${ROOT}" -profile test -stub-run -ansi-log false \
  --workflow chipseq --chipseq_run_mode annotation \
  --chipseq_annotation_peaks "${TEST_ROOT}/fixture_work/fixture.peaks.bed" \
  --chipseq_annotation_peak_manifest "${TEST_ROOT}/fixture_work/peak_manifest.json" \
  --chipseq_annotation_reference "${TEST_ROOT}/fixture_work/reference.fa" \
  --chipseq_annotation_reference_manifest "${TEST_ROOT}/fixture_work/reference_manifest.json" \
  --chipseq_annotation_gtf "${TEST_ROOT}/fixture_work/annotation.gtf" \
  --outdir "${TEST_ROOT}/top_level_results"
