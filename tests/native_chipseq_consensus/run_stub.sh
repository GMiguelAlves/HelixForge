#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TEST_ROOT="${ROOT}/tests/native_chipseq_consensus"
python3 "${TEST_ROOT}/generate_fixture.py" --outdir "${TEST_ROOT}/fixture_work"
"${NEXTFLOW_BIN:-nextflow}" run "${TEST_ROOT}/main.nf" -c "${TEST_ROOT}/nextflow.config" \
  -stub-run -ansi-log false --chipseq_run_mode consensus --chipseq_consensus_method union
"${NEXTFLOW_BIN:-nextflow}" run "${TEST_ROOT}/main.nf" -c "${TEST_ROOT}/nextflow.config" \
  -stub-run -ansi-log false --chipseq_run_mode idr
