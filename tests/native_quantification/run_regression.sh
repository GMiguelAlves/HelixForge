#!/usr/bin/env bash

set -euo pipefail

project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
nextflow_bin=${NEXTFLOW_BIN:-nextflow}
nextflow_jar=${NEXTFLOW_JAR:-}
image=${SALMON_CONTAINER:-quay.io/biocontainers/salmon@sha256:f83ebb158845ee8138d793347f83b92c75e83c58dd8f4600c6fea2a2453ef08e}
case_root="${project_root}/results/test/native-quantification-regression"
fixture_root="${project_root}/tests/fixtures/native_quantification"
legacy_dir="${case_root}/legacy"
native_dir="${case_root}/native"
nextflow_out="${case_root}/nextflow"

case "$case_root" in
    "${project_root}"/results/test/*) ;;
    *) echo "Unsafe test path: $case_root" >&2; exit 2 ;;
esac
rm -rf "$case_root"

run_nextflow() {
    if [[ -n "$nextflow_jar" ]]; then
        java -jar "$nextflow_jar" "$@"
    else
        "$nextflow_bin" "$@"
    fi
}

mkdir -p "$legacy_dir/index" "$legacy_dir/quant" "$native_dir" "$nextflow_out"

start_legacy=$(date +%s%N)
docker run --rm \
    -v "${case_root}:/data" \
    -v "${fixture_root}:/fixtures:ro" \
    "$image" \
    salmon index \
        -t /fixtures/transcriptome.fa \
        -i /data/legacy/index \
        -p 1 \
        -k 31 \
        > "${legacy_dir}/salmon_index.log" 2>&1

docker run --rm \
    -v "${case_root}:/data" \
    -v "${fixture_root}:/fixtures:ro" \
    "$image" \
    salmon quant \
        -i /data/legacy/index \
        -l A \
        -1 /fixtures/reads_R1.fastq \
        -2 /fixtures/reads_R2.fastq \
        -p 1 \
        --validateMappings \
        -o /data/legacy/quant \
        > "${legacy_dir}/salmon_quant.process.log" 2>&1
end_legacy=$(date +%s%N)

start_native=$(date +%s%N)
run_nextflow run "${project_root}/tests/native_quantification/main.nf" \
    -c "${project_root}/tests/native_quantification/nextflow.config" \
    -profile docker -ansi-log false \
    --transcriptome "${fixture_root}/transcriptome.fa" \
    --read1 "${fixture_root}/reads_R1.fastq" \
    --read2 "${fixture_root}/reads_R2.fastq" \
    --target_root "$native_dir" \
    --docker_bind_root "$case_root" \
    --outdir "$nextflow_out"
end_native=$(date +%s%N)

python3 "${project_root}/tests/native_quantification/compare_salmon_outputs.py" \
    "${legacy_dir}/quant" \
    "${native_dir}/quants/SYNTHETIC/synthetic_sample" \
    "${case_root}/comparison.tsv"

legacy_ms=$(((end_legacy - start_legacy) / 1000000))
native_ms=$(((end_native - start_native) / 1000000))
printf 'implementation\telapsed_ms\nlegacy_command\t%s\nnextflow_native\t%s\n' \
    "$legacy_ms" "$native_ms" > "${case_root}/benchmark.tsv"

echo '[OK] Salmon legacy and native outputs are semantically equivalent.'
echo "[OK] Comparison: ${case_root}/comparison.tsv"
echo "[OK] Benchmark: ${case_root}/benchmark.tsv"
