#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
nextflow_bin="${NEXTFLOW:-nextflow}"
image="${RNASEQ_REPORT_TEST_IMAGE:-ghcr.io/gmiguelalves/helixforge-rnaseq-report:1.0.0}"

rm -rf -- "${script_dir}/real_results" "${script_dir}/real_work"
RNASEQ_REPORT_TEST_IMAGE="${image}" "${nextflow_bin}" run "${script_dir}/main.nf" \
  -c "${script_dir}/real.config" -ansi-log false
python3 "${script_dir}/validate_real_report.py" \
  "${script_dir}/real_results/rnaseq/090-search-gene/results"
