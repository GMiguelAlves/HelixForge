#!/usr/bin/env bash

set -euo pipefail

project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
nextflow_bin=${NEXTFLOW_BIN:-nextflow}
nextflow_jar=${NEXTFLOW_JAR:-}
case_root="${project_root}/results/test/trim-galore-mock-integration"
input_dir="${case_root}/input"
native_dir="${case_root}/native"
nextflow_out="${case_root}/nextflow"

run_nextflow() {
    if [[ -n "$nextflow_jar" ]]; then
        java -jar "$nextflow_jar" "$@"
    else
        "$nextflow_bin" "$@"
    fi
}

mkdir -p "$input_dir" "$native_dir" "$nextflow_out"
gzip -n -c "${project_root}/tests/fixtures/trim_galore/input_R1.fastq" > "${input_dir}/input_R1.fastq.gz"
gzip -n -c "${project_root}/tests/fixtures/trim_galore/input_R2.fastq" > "${input_dir}/input_R2.fastq.gz"

PATH="${project_root}/tests/fixtures/trim_galore/bin:${PATH}" \
run_nextflow run "${project_root}/tests/native_trim_galore/main.nf" \
    -c "${project_root}/tests/native_trim_galore/nextflow.config" \
    -profile local \
    -ansi-log false \
    --read1 "${input_dir}/input_R1.fastq.gz" \
    --read2 "${input_dir}/input_R2.fastq.gz" \
    --target_dir "$native_dir" \
    --outdir "$nextflow_out"

gzip -t "${native_dir}/synthetic_R1_trimmed.fastq.gz"
gzip -t "${native_dir}/synthetic_R2_trimmed.fastq.gz"
test -s "${native_dir}/input_R1.fastq.gz_trimming_report.txt"
test -s "${native_dir}/input_R2.fastq.gz_trimming_report.txt"
test -s "${nextflow_out}/pipeline_info/native_qc/trim_galore/SYNTHETIC.synthetic_sample.synthetic_run.trim_galore.trim_galore.done"
test -s "${nextflow_out}/pipeline_info/native_qc/trim_galore/SYNTHETIC.synthetic_sample.synthetic_run.trim_galore.versions.yml"

echo "[OK] Native module command, outputs, reports, versions and materialization validated."
