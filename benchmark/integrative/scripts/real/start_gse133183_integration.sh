#!/usr/bin/env bash
set -euo pipefail

if [[ "$#" -ne 9 ]]; then
  echo "Usage: $0 REPO BENCHMARK_ROOT ALLOWED_SCRATCH_ROOT RNA_MANIFEST CHIP_MANIFEST PYTHON_RUNTIME JAVA NEXTFLOW_JAR COMMIT" >&2
  exit 2
fi

repo_root="$1"
benchmark_root="$2"
allowed_scratch_root="$3"
rna_manifest="$4"
chip_manifest="$5"
python_runtime="$6"
java_bin="$7"
nextflow_jar="$8"
expected_commit="$9"
log_dir="$benchmark_root/logs"
pid_file="$log_dir/integration-driver.pid"

mkdir -p "$log_dir"
if [[ -e "$pid_file" ]]; then
  old_pid=$(cat "$pid_file")
  if kill -0 "$old_pid" 2>/dev/null; then
    echo "Integration driver is already running: $old_pid" >&2
    exit 2
  fi
fi

nohup env \
  HELIXFORGE_REPO_ROOT="$repo_root" \
  HELIXFORGE_BENCHMARK_ROOT="$benchmark_root" \
  HELIXFORGE_ALLOWED_SCRATCH_ROOT="$allowed_scratch_root" \
  HELIXFORGE_RNA_MANIFEST="$rna_manifest" \
  HELIXFORGE_CHIP_MANIFEST="$chip_manifest" \
  HELIXFORGE_PYTHON_RUNTIME="$python_runtime" \
  HELIXFORGE_JAVA="$java_bin" \
  HELIXFORGE_NEXTFLOW_JAR="$nextflow_jar" \
  HELIXFORGE_EXECUTION_COMMIT="$expected_commit" \
  bash "$repo_root/benchmark/integrative/scripts/real/run_gse133183_integration.sh" \
  > "$log_dir/integration-driver.log" 2>&1 < /dev/null &
pid=$!
printf '%s\n' "$pid" > "$pid_file"
printf '%s\n' "$pid"
