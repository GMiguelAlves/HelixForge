#!/usr/bin/env bash

set -euo pipefail

project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
nextflow_bin=${NEXTFLOW_BIN:-nextflow}
nextflow_jar=${NEXTFLOW_JAR:-}
case_root="${project_root}/results/test/native-qc-regression"
input_dir="${case_root}/input"
legacy_dir="${case_root}/legacy"
native_dir="${case_root}/native"
nextflow_out="${case_root}/nextflow"
mock_bin="${project_root}/tests/fixtures/native_qc/bin"
trim_mock_bin="${project_root}/tests/fixtures/trim_galore/bin"

run_nextflow() {
    if [[ -n "$nextflow_jar" ]]; then
        java -jar "$nextflow_jar" "$@"
    else
        "$nextflow_bin" "$@"
    fi
}

mkdir -p "$input_dir" "$legacy_dir" "$native_dir" "$nextflow_out"
for run in run_a run_b; do
    for mate in R1 R2; do
        gzip -n -c "${project_root}/tests/fixtures/native_qc/${run}_${mate}.fastq" \
            > "${input_dir}/${run}_${mate}.fastq.gz"
    done
done

start_legacy=$(date +%s%N)
mkdir -p \
    "${legacy_dir}/fastqc_raw" \
    "${legacy_dir}/trimmed_runs" \
    "${legacy_dir}/fastqc_trimmed_runs" \
    "${legacy_dir}/trimmed_merged" \
    "${legacy_dir}/fastqc_merged" \
    "${legacy_dir}/multiqc_030"

for run in run_a run_b; do
    for mate in R1 R2; do
        "$mock_bin/fastqc" "${input_dir}/${run}_${mate}.fastq.gz" \
            --outdir "${legacy_dir}/fastqc_raw" --threads 1
    done
    "$trim_mock_bin/trim_galore" --paired --quality 20 --length 20 --cores 1 \
        --output_dir "${legacy_dir}/trimmed_runs" \
        "${input_dir}/${run}_R1.fastq.gz" "${input_dir}/${run}_R2.fastq.gz"
    mv "${legacy_dir}/trimmed_runs/${run}_R1_val_1.fq.gz" \
        "${legacy_dir}/trimmed_runs/sample_${run}_R1_trimmed.fastq.gz"
    mv "${legacy_dir}/trimmed_runs/${run}_R2_val_2.fq.gz" \
        "${legacy_dir}/trimmed_runs/sample_${run}_R2_trimmed.fastq.gz"
    for mate in R1 R2; do
        "$mock_bin/fastqc" "${legacy_dir}/trimmed_runs/sample_${run}_${mate}_trimmed.fastq.gz" \
            --outdir "${legacy_dir}/fastqc_trimmed_runs" --threads 1
    done
done

cat \
    "${legacy_dir}/trimmed_runs/sample_run_a_R1_trimmed.fastq.gz" \
    "${legacy_dir}/trimmed_runs/sample_run_b_R1_trimmed.fastq.gz" \
    > "${legacy_dir}/trimmed_merged/sample_R1_trimmed.fastq.gz"
cat \
    "${legacy_dir}/trimmed_runs/sample_run_a_R2_trimmed.fastq.gz" \
    "${legacy_dir}/trimmed_runs/sample_run_b_R2_trimmed.fastq.gz" \
    > "${legacy_dir}/trimmed_merged/sample_R2_trimmed.fastq.gz"

for mate in R1 R2; do
    "$mock_bin/fastqc" "${legacy_dir}/trimmed_merged/sample_${mate}_trimmed.fastq.gz" \
        --outdir "${legacy_dir}/fastqc_merged" --threads 1
done
"$mock_bin/multiqc" \
    "${legacy_dir}/fastqc_raw"/*_fastqc.zip \
    "${legacy_dir}/fastqc_trimmed_runs"/*_fastqc.zip \
    "${legacy_dir}/fastqc_merged"/*_fastqc.zip \
    -o "${legacy_dir}/multiqc_030" -n TEST_multiqc_030.html
end_legacy=$(date +%s%N)

start_native=$(date +%s%N)
PATH="${mock_bin}:${trim_mock_bin}:${PATH}" \
run_nextflow run "${project_root}/tests/native_qc/main.nf" \
    -c "${project_root}/tests/native_qc/nextflow.config" \
    -ansi-log false \
    --input_dir "$input_dir" \
    --target_root "$native_dir" \
    --outdir "$nextflow_out"
end_native=$(date +%s%N)

comparison="${case_root}/comparison.tsv"
printf 'artifact\tlegacy_sha256\tnative_sha256\tresult\n' > "$comparison"
compare_file() {
    local artifact=$1
    local legacy_file=$2
    local native_file=$3
    local legacy_sha native_sha result
    legacy_sha=$(sha256sum "$legacy_file" | awk '{ print $1 }')
    native_sha=$(sha256sum "$native_file" | awk '{ print $1 }')
    result=FAIL
    [[ "$legacy_sha" == "$native_sha" ]] && result=PASS
    printf '%s\t%s\t%s\t%s\n' "$artifact" "$legacy_sha" "$native_sha" "$result" >> "$comparison"
    [[ "$result" == PASS ]]
}

compare_file merged_R1 \
    "${legacy_dir}/trimmed_merged/sample_R1_trimmed.fastq.gz" \
    "${native_dir}/trimmed_merged/sample_R1_trimmed.fastq.gz"
compare_file merged_R2 \
    "${legacy_dir}/trimmed_merged/sample_R2_trimmed.fastq.gz" \
    "${native_dir}/trimmed_merged/sample_R2_trimmed.fastq.gz"
compare_file multiqc_table \
    "${legacy_dir}/multiqc_030/TEST_multiqc_030_data/multiqc_fastqc.txt" \
    "${native_dir}/multiqc_030/TEST_multiqc_030_data/multiqc_fastqc.txt"

for phase in fastqc_raw fastqc_trimmed_runs fastqc_merged; do
    for legacy_report in "${legacy_dir}/${phase}"/*_fastqc.html; do
        name=$(basename "$legacy_report")
        compare_file "${phase}/${name}" "$legacy_report" "${native_dir}/${phase}/${name}"
    done
done

legacy_ms=$(((end_legacy - start_legacy) / 1000000))
native_ms=$(((end_native - start_native) / 1000000))
printf 'implementation\telapsed_ms\nlegacy_commands\t%s\nnextflow_native\t%s\n' \
    "$legacy_ms" "$native_ms" > "${case_root}/benchmark.tsv"

echo "[OK] Native QC orchestration matches the legacy command sequence."
echo "[OK] Comparison: ${comparison}"
echo "[OK] Benchmark: ${case_root}/benchmark.tsv"
