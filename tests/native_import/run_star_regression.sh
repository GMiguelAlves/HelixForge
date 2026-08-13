#!/usr/bin/env bash

set -euo pipefail

project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
source "${project_root}/tests/lib/materialize_rnaseq_legacy.sh"
nextflow_bin=${NEXTFLOW_BIN:-nextflow}
nextflow_jar=${NEXTFLOW_JAR:-}
fixture_root="${project_root}/tests/fixtures/native_import"
case_root="${project_root}/results/test/native-import-star-regression"
legacy_root="${case_root}/legacy_root"
legacy_out="${case_root}/legacy"
native_out="${case_root}/native"
nextflow_out="${case_root}/nextflow"
legacy_runtime=${HELIXFORGE_STAR_LEGACY_RUNTIME:-container}

run_nextflow() {
    if [[ -n "$nextflow_jar" ]]; then
        java -jar "$nextflow_jar" "$@"
    else
        "$nextflow_bin" "$@"
    fi
}

case "$case_root" in
    "${project_root}"/results/test/*) ;;
    *) echo "Unsafe test path: $case_root" >&2; exit 2 ;;
esac
rm -rf "$case_root"
mkdir -p "$legacy_root/SYNTHETIC/sample_a" "$legacy_root/SYNTHETIC/sample_b" "$legacy_out" "$native_out" "$nextflow_out"
materialize_rnaseq_legacy "$project_root" \
    'scripts/050-quantification/import_star_counts.py' \
    "$case_root/legacy_source/import_star_counts.py"
cp "$fixture_root/star/sample_a/ReadsPerGene.out.tab" "$legacy_root/SYNTHETIC/sample_a/"
cp "$fixture_root/star/sample_b/ReadsPerGene.out.tab" "$legacy_root/SYNTHETIC/sample_b/"

start_legacy=$(date +%s%N)
if [[ "$legacy_runtime" == 'host' ]]; then
    python3 -c 'import pandas; assert pandas.__version__.startswith("2.1.4")'
    python3 "${case_root}/legacy_source/import_star_counts.py" \
        --metadata "${fixture_root}/metadata.csv" \
        --quant-root "$legacy_root" \
        --output-dir "$legacy_out" \
        --count-column unstranded > "${case_root}/legacy.log" 2>&1
elif [[ "$legacy_runtime" == 'container' ]]; then
    docker run --rm \
        -v "${project_root}:/project:ro" \
        -v "${case_root}:/case" \
        -v "${fixture_root}:/fixtures:ro" \
        python:3.11.9-slim-bookworm \
        sh -c 'pip install --disable-pip-version-check --no-cache-dir pandas==2.1.4 >/case/pip.log && python /case/legacy_source/import_star_counts.py --metadata /fixtures/metadata.csv --quant-root /case/legacy_root --output-dir /case/legacy --count-column unstranded' \
        > "${case_root}/legacy.log" 2>&1
else
    echo "HELIXFORGE_STAR_LEGACY_RUNTIME must be host or container" >&2
    exit 2
fi
end_legacy=$(date +%s%N)

start_native=$(date +%s%N)
run_nextflow run "${project_root}/tests/native_import/main.nf" \
    -c "${project_root}/tests/native_import/nextflow.config" \
    -profile local -ansi-log false \
    --provider star \
    --fixture_root "$fixture_root" \
    --target_root "$native_out" \
    --outdir "$nextflow_out" \
    --trace_file "${case_root}/native_trace.tsv"
end_native=$(date +%s%N)

cp "${nextflow_out}/pipeline_info/native_import/star_import/import_manifest.json" "$native_out/import_manifest.json"
python3 "${project_root}/tests/native_import/compare_outputs.py" \
    "$legacy_out" "$native_out" --provider star --output "${case_root}/comparison.tsv"

legacy_ms=$(((end_legacy - start_legacy) / 1000000))
native_ms=$(((end_native - start_native) / 1000000))
printf 'implementation\telapsed_ms\tthreads\nlegacy_star_import\t%s\t1\nnextflow_import_api\t%s\t1\n' \
    "$legacy_ms" "$native_ms" > "${case_root}/benchmark.tsv"

echo '[OK] STAR legacy and Import API outputs are semantically equivalent.'
echo "[OK] Comparison: ${case_root}/comparison.tsv"
echo "[OK] Benchmark: ${case_root}/benchmark.tsv"
