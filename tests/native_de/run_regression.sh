#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
IMAGE="${DESEQ2_TEST_IMAGE:-helixforge-deseq2:test}"
NXF_BIN="${NEXTFLOW:-nextflow}"
if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "[SKIP] Missing validated DESeq2 image: $IMAGE" >&2
  echo "Build containers/deseq2/Dockerfile or use DESEQ2_TEST_IMAGE." >&2
  exit 2
fi
cd "$ROOT"
mkdir -p tests/results/native_de/legacy tests/results/native_de/native
docker run --rm -v "$ROOT:/workspace" -w /workspace "$IMAGE" \
  Rscript pipelines/rnaseq/legacy/scripts/060-deg-analysis/deseq2_analysis.R \
  --counts tests/fixtures/native_de/counts_matrix.tsv \
  --samples tests/fixtures/native_de/quant_samples.tsv \
  --gff tests/fixtures/native_de/annotation.gff \
  --output-dir tests/results/native_de/legacy \
  --analysis-id golden --test-variables condition --design-covariates batch
"$NXF_BIN" run tests/native_de/main.nf -profile docker,test -ansi-log false \
  --deseq2_container "$IMAGE" --de_adapter_container python:3.11-slim \
  --outdir tests/results/native_de/native -work-dir work/tests/native-de-regression
python3 tests/native_de/compare_results.py \
  tests/results/native_de/legacy tests/results/native_de/legacy_layout
