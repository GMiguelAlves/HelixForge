#!/usr/bin/env bash

set -euo pipefail

CONFIG_FILE="${1:-config/pipeline_config.sh}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"
load_chipseq_config "${CONFIG_FILE}"

missing=0

check_cmd() {
  local cmd="$1"
  if command -v "${cmd}" >/dev/null 2>&1; then
    printf 'ok\t%s\n' "${cmd}"
  else
    printf 'missing\t%s\n' "${cmd}"
    missing=1
  fi
}

echo "Checking core runtime commands"
check_cmd bash
check_cmd gzip
check_cmd "${PYTHON_BIN}"
check_cmd "${RSCRIPT_BIN}"

echo
echo "Checking ChIP-seq tools"
check_cmd fastqc
check_cmd multiqc
check_cmd samtools
check_cmd bedtools
check_cmd "${PEAK_CALLER}"

case "${TRIM_TOOL}" in
  fastp) check_cmd fastp ;;
  trim_galore) check_cmd trim_galore ;;
esac

case "${ALIGNER}" in
  bowtie2)
    check_cmd bowtie2
    check_cmd bowtie2-build
    ;;
  bwa)
    check_cmd bwa
    ;;
esac

echo
echo "Checking optional tools"
for cmd in bamCoverage plotFingerprint bamPEFragmentSize; do
  if command -v "${cmd}" >/dev/null 2>&1; then
    printf 'ok\t%s\n' "${cmd}"
  else
    printf 'optional-missing\t%s\n' "${cmd}"
  fi
done

if [[ "${PIPELINE_EXECUTOR:-${RUN_MODE:-slurm}}" == "slurm" ]]; then
  echo
  echo "Checking Slurm"
  check_cmd sbatch
fi

if [[ "${missing}" -ne 0 ]]; then
  echo
  echo "One or more required commands are missing for the current config." >&2
  exit 1
fi

echo
echo "Install check passed for the current config."
