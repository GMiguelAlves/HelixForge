#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
IMAGE="${DESEQ2_TEST_IMAGE:-helixforge-deseq2:test}"
ADAPTER_IMAGE="${DE_ADAPTER_TEST_IMAGE:-python:3.11.9-slim-bookworm}"
NXF_BIN="${NEXTFLOW:-nextflow}"
NXF_JAR="${NEXTFLOW_JAR:-}"

run_nextflow() {
  if [[ -n "$NXF_JAR" ]]; then
    java -jar "$NXF_JAR" "$@"
  else
    "$NXF_BIN" "$@"
  fi
}
if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "[SKIP] Missing validated DESeq2 image: $IMAGE" >&2
  exit 2
fi
cd "$ROOT"
SPEC="$(mktemp --suffix=.json)"
cp tests/fixtures/native_de/analysis_spec.json "$SPEC"
COMMON=(run tests/native_de/main.nf -profile docker,test -ansi-log false -resume
  --deseq2_container "$IMAGE" --de_adapter_container "$ADAPTER_IMAGE"
  --de_analysis_spec "$SPEC" --outdir tests/results/native_de/cache
  -work-dir work/tests/native-de-cache)
run_nextflow "${COMMON[@]}"
python3 - "$SPEC" <<'PY'
import json, sys
path = sys.argv[1]
doc = json.load(open(path))
doc["contrasts"][0]["description"] = "cache-only contrast change"
open(path, "w").write(json.dumps(doc, separators=(",", ":")) + "\n")
PY
run_nextflow "${COMMON[@]}"
TRACE=tests/results/native_de/cache/pipeline_info/execution_trace.tsv
awk -F '\t' '$4 ~ /DESEQ2_MODEL/ {seen=1; if ($5 != "CACHED") bad=1} END {exit (!seen || bad)}' "$TRACE"
awk -F '\t' '$4 ~ /DESEQ2_CONTRAST/ && $5 != "CACHED" {seen=1} END {exit !seen}' "$TRACE"
