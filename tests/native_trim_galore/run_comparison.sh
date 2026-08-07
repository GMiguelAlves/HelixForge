#!/usr/bin/env bash

set -euo pipefail

project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
nextflow_bin=${NEXTFLOW_BIN:-nextflow}
image=${TRIM_GALORE_CONTAINER:-quay.io/biocontainers/trim-galore:0.6.10--hdfd78af_0}
case_root="${project_root}/results/test/trim-galore-comparison"
input_dir="${case_root}/input"
legacy_dir="${case_root}/legacy"
native_dir="${case_root}/native"
nextflow_out="${case_root}/nextflow"

mkdir -p "$input_dir" "$legacy_dir" "$native_dir" "$nextflow_out"
gzip -n -c "${project_root}/tests/fixtures/trim_galore/input_R1.fastq" > "${input_dir}/input_R1.fastq.gz"
gzip -n -c "${project_root}/tests/fixtures/trim_galore/input_R2.fastq" > "${input_dir}/input_R2.fastq.gz"

start_legacy=$(date +%s%N)
docker run --rm \
    -v "${case_root}:/data" \
    "$image" \
    trim_galore --paired \
        --quality 20 \
        --length 20 \
        --cores 2 \
        --output_dir /data/legacy \
        /data/input/input_R1.fastq.gz \
        /data/input/input_R2.fastq.gz
end_legacy=$(date +%s%N)

mv "${legacy_dir}/input_R1_val_1.fq.gz" "${legacy_dir}/synthetic_R1_trimmed.fastq.gz"
mv "${legacy_dir}/input_R2_val_2.fq.gz" "${legacy_dir}/synthetic_R2_trimmed.fastq.gz"

start_native=$(date +%s%N)
"$nextflow_bin" run "${project_root}/tests/native_trim_galore/main.nf" \
    -c "${project_root}/tests/native_trim_galore/nextflow.config" \
    -profile docker \
    -ansi-log false \
    --read1 "${input_dir}/input_R1.fastq.gz" \
    --read2 "${input_dir}/input_R2.fastq.gz" \
    --target_dir "$native_dir" \
    --docker_bind_root "$case_root" \
    --outdir "$nextflow_out"
end_native=$(date +%s%N)

for mate in R1 R2; do
    legacy_file="${legacy_dir}/synthetic_${mate}_trimmed.fastq.gz"
    native_file="${native_dir}/synthetic_${mate}_trimmed.fastq.gz"
    legacy_content=$(gzip -dc "$legacy_file" | sha256sum | awk '{print $1}')
    native_content=$(gzip -dc "$native_file" | sha256sum | awk '{print $1}')
    [[ "$legacy_content" == "$native_content" ]]

    legacy_reads=$(gzip -dc "$legacy_file" | awk 'END { print NR / 4 }')
    native_reads=$(gzip -dc "$native_file" | awk 'END { print NR / 4 }')
    [[ "$legacy_reads" == "$native_reads" ]]

    printf '%s\t%s\t%s\n' "$mate" "$legacy_content" "$legacy_reads"
done > "${case_root}/scientific_comparison.tsv"

for report in input_R1.fastq.gz_trimming_report.txt input_R2.fastq.gz_trimming_report.txt; do
    test -s "${legacy_dir}/${report}"
    test -s "${native_dir}/${report}"
done

legacy_ms=$(((end_legacy - start_legacy) / 1000000))
native_ms=$(((end_native - start_native) / 1000000))
printf 'implementation\telapsed_ms\nlegacy_command\t%s\nnextflow_native\t%s\n' \
    "$legacy_ms" "$native_ms" > "${case_root}/benchmark.tsv"

echo "[OK] Native and legacy Trim Galore outputs are scientifically equivalent."
echo "[OK] Comparison: ${case_root}/scientific_comparison.tsv"
echo "[OK] Benchmark: ${case_root}/benchmark.tsv"
