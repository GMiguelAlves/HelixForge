#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
NXF_BIN="${NEXTFLOW:-nextflow}"
cd "$ROOT"
"$NXF_BIN" run tests/native_de/main.nf \
  -profile test -stub-run -ansi-log false \
  --outdir tests/results/native_de/stub \
  -work-dir work/tests/native-de-stub
test -s tests/results/native_de/legacy_layout/DEGs_all_results.tsv
test -s tests/results/native_de/legacy_layout/de_manifest.json
