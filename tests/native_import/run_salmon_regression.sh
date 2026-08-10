#!/usr/bin/env bash

set -euo pipefail

project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
nextflow_bin=${NEXTFLOW_BIN:-nextflow}
fixture_root="${project_root}/tests/fixtures/native_import"
case_root="${project_root}/results/test/native-import-salmon-regression"
legacy_root="${case_root}/legacy_root"
legacy_out="${case_root}/legacy"
native_out="${case_root}/native"
nextflow_out="${case_root}/nextflow"
image=${HELIXFORGE_IMPORT_CONTAINER:-ghcr.io/gmiguelalves/helixforge-import:1.0.0}

case "$case_root" in
    "${project_root}"/results/test/*) ;;
    *) echo "Unsafe test path: $case_root" >&2; exit 2 ;;
esac
rm -rf "$case_root"
mkdir -p "$legacy_root/SYNTHETIC/sample_a" "$legacy_root/SYNTHETIC/sample_b" "$legacy_out" "$native_out" "$nextflow_out"
cp "$fixture_root/salmon/sample_a/quant.sf" "$legacy_root/SYNTHETIC/sample_a/"
cp "$fixture_root/salmon/sample_b/quant.sf" "$legacy_root/SYNTHETIC/sample_b/"

start_legacy=$(date +%s%N)
docker run --rm \
    -v "${project_root}:/project:ro" \
    -v "${case_root}:/case" \
    -v "${fixture_root}:/fixtures:ro" \
    "$image" \
    Rscript /project/pipelines/rnaseq/legacy/scripts/050-quantification/txtimport_quant.R \
        --metadata /fixtures/metadata_single.csv \
        --quant-root /case/legacy_root \
        --gtf /fixtures/annotation.gtf \
        --output-dir /case/legacy \
        > "${case_root}/legacy.log" 2>&1
end_legacy=$(date +%s%N)

start_native=$(date +%s%N)
"$nextflow_bin" run "${project_root}/tests/native_import/main.nf" \
    -c "${project_root}/tests/native_import/nextflow.config" \
    -profile docker -ansi-log false \
    --provider salmon \
    --fixture_root "$fixture_root" \
    --metadata_file "$fixture_root/metadata_single.csv" \
    --target_root "$native_out" \
    --outdir "$nextflow_out" \
    --trace_file "${case_root}/native_trace.tsv" \
    --import_source_container "$image" \
    --tx2gene_container "$image" \
    --tximport_container "$image"
end_native=$(date +%s%N)

cp "${nextflow_out}/pipeline_info/native_import/tximport/import_manifest.json" "$native_out/import_manifest.json"
python3 "${project_root}/tests/native_import/compare_outputs.py" \
    "$legacy_out" "$native_out" --provider salmon --output "${case_root}/comparison.tsv"
docker run --rm \
    -v "${project_root}:/project:ro" \
    -v "${case_root}:/case:ro" \
    "$image" \
    Rscript /project/tests/native_import/validate_experiment.R \
        /case/native/summarized_experiment.rds \
        /case/native/counts_matrix.tsv \
        /case/native/tpm_matrix.tsv \
        /case/native/length_matrix.tsv \
        /case/native/quant_samples.tsv \
        > "${case_root}/experiment_validation.txt"

legacy_ms=$(((end_legacy - start_legacy) / 1000000))
native_ms=$(((end_native - start_native) / 1000000))
printf 'implementation\telapsed_ms\tthreads\nlegacy_tximport\t%s\t1\nnextflow_import_api\t%s\t1\n' \
    "$legacy_ms" "$native_ms" > "${case_root}/benchmark.tsv"

echo '[OK] Salmon legacy and Import API outputs are semantically equivalent.'
echo "[OK] Comparison: ${case_root}/comparison.tsv"
echo "[OK] Benchmark: ${case_root}/benchmark.tsv"
