#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TEST_ROOT="${ROOT}/tests/native_chipseq_differential_binding"
python3 "${TEST_ROOT}/generate_fixture.py" --outdir "${TEST_ROOT}/fixture_work"
"${NEXTFLOW_BIN:-nextflow}" run "${TEST_ROOT}/main.nf" -c "${TEST_ROOT}/nextflow.config" -stub-run -ansi-log false
"${NEXTFLOW_BIN:-nextflow}" run "${ROOT}" -profile test -stub-run -ansi-log false \
  --workflow chipseq --chipseq_run_mode differential_binding \
  --chipseq_consensus_method union --chipseq_db_spec "${TEST_ROOT}/fixture_work/db_spec.json" \
  --outdir "${TEST_ROOT}/top_level_results"
