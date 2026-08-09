#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
IMAGE="${DESEQ2_TEST_IMAGE:-omicsflow-deseq2:test}"
NXF_BIN="${NEXTFLOW:-nextflow}"
if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "[SKIP] Missing validated DESeq2 image: $IMAGE" >&2
  exit 2
fi
cd "$ROOT"
SPEC="$(mktemp --suffix=.json)"
cp tests/fixtures/native_de/analysis_spec.json "$SPEC"
COMMON=(run tests/native_de/main.nf -profile docker,test -ansi-log false -resume
  --deseq2_container "$IMAGE" --de_adapter_container python:3.11-slim
  --de_analysis_spec "$SPEC" --outdir tests/results/native_de/cache
  -work-dir work/tests/native-de-cache)
"$NXF_BIN" "${COMMON[@]}"
python3 - "$SPEC" <<'PY'
import json, sys
path = sys.argv[1]
doc = json.load(open(path))
doc["contrasts"][0]["description"] = "cache-only contrast change"
open(path, "w").write(json.dumps(doc, separators=(",", ":")) + "\n")
PY
"$NXF_BIN" "${COMMON[@]}"
TRACE=tests/results/native_de/cache/pipeline_info/execution_trace.tsv
awk -F '\t' '$4 ~ /DESEQ2_MODEL/ {seen=1; if ($5 != "CACHED") bad=1} END {exit (!seen || bad)}' "$TRACE"
awk -F '\t' '$4 ~ /DESEQ2_CONTRAST/ && $5 != "CACHED" {seen=1} END {exit !seen}' "$TRACE"
