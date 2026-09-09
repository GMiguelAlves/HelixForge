#!/usr/bin/env bash
set -euo pipefail

repo_root=${HELIXFORGE_REPO_ROOT:?HELIXFORGE_REPO_ROOT is required}
benchmark_root=${HELIXFORGE_BENCHMARK_ROOT:?HELIXFORGE_BENCHMARK_ROOT is required}
allowed_scratch_root=${HELIXFORGE_ALLOWED_SCRATCH_ROOT:?HELIXFORGE_ALLOWED_SCRATCH_ROOT is required}
rna_manifest=${HELIXFORGE_RNA_MANIFEST:?HELIXFORGE_RNA_MANIFEST is required}
chip_manifest=${HELIXFORGE_CHIP_MANIFEST:?HELIXFORGE_CHIP_MANIFEST is required}
python_runtime=${HELIXFORGE_PYTHON_RUNTIME:?HELIXFORGE_PYTHON_RUNTIME is required}
java_bin=${HELIXFORGE_JAVA:?HELIXFORGE_JAVA is required}
nextflow_jar=${HELIXFORGE_NEXTFLOW_JAR:?HELIXFORGE_NEXTFLOW_JAR is required}
expected_commit=${HELIXFORGE_EXECUTION_COMMIT:?HELIXFORGE_EXECUTION_COMMIT is required}
mkdir -p "$benchmark_root/logs"
trap 'rc=$?; printf "%s\n" "$rc" > "$benchmark_root/logs/integration-driver.exit"' EXIT

[[ -z "${SLURM_JOB_ID:-}" ]] || { echo "Nextflow driver must run on the Slurm management node" >&2; exit 2; }
[[ "$(dirname "$benchmark_root")" == "$allowed_scratch_root" ]] || {
  echo "Refusing benchmark root outside the declared runtime scope" >&2
  exit 2
}
[[ "$(basename "$benchmark_root")" == helixforge-integrative-real-* ]] || {
  echo "Refusing unexpected benchmark directory name" >&2
  exit 2
}

case_root="$benchmark_root/cases/integration"
results="$case_root/results"
logs="$case_root/logs"
work="$case_root/work"
nxf_home="$case_root/nxf-home"
cache="$case_root/cache"

[[ -d "$repo_root/.git" ]] || { echo "Repository checkout is missing .git" >&2; exit 2; }
[[ -x "$python_runtime/bin/python3" ]] || { echo "Python runtime is not executable" >&2; exit 2; }
[[ -x "$java_bin" ]] || { echo "Java runtime is not executable" >&2; exit 2; }
[[ -s "$nextflow_jar" ]] || { echo "Nextflow runtime is missing or empty" >&2; exit 2; }
[[ -s "$rna_manifest" ]] || { echo "RNA terminal manifest is missing or empty" >&2; exit 2; }
[[ -s "$chip_manifest" ]] || { echo "ChIP terminal manifest is missing or empty" >&2; exit 2; }
[[ ! -e "$case_root" ]] || { echo "Integration case directory already exists" >&2; exit 2; }

actual_commit=$(git -C "$repo_root" rev-parse HEAD)
[[ "$actual_commit" == "$expected_commit" ]] || {
  echo "Repository commit mismatch: expected $expected_commit, got $actual_commit" >&2
  exit 2
}
[[ -z "$(git -C "$repo_root" status --porcelain=v1)" ]] || {
  echo "Repository checkout is not clean" >&2
  exit 2
}

mkdir -p "$results" "$logs" "$work" "$nxf_home" "$cache" "$case_root/frozen_inputs"
cp "$repo_root/assets/integration/harmonization_policy.v1.json" "$case_root/frozen_inputs/harmonization_policy.json"
cp "$repo_root/assets/integration/interpretation_policy.v1.json" "$case_root/frozen_inputs/interpretation_policy.json"
cp "$repo_root/assets/integration/mark_roles.v1.tsv" "$case_root/frozen_inputs/mark_roles.tsv"
cp "$repo_root/assets/integration/prioritization_context.template.tsv" "$case_root/frozen_inputs/prioritization_context.tsv"
cp "$repo_root/assets/integration/functional_annotation.template.tsv" "$case_root/frozen_inputs/functional_annotation.tsv"

printf '%s\n' "$actual_commit" > "$case_root/repository_commit.txt"
git -C "$repo_root" status --porcelain=v1 > "$case_root/repository_status.txt"
(
  cd "$case_root/frozen_inputs"
  sha256sum ./*
) > "$case_root/frozen_input_checksums.sha256"
(
  cd "$(dirname "$rna_manifest")"
  sha256sum "$(basename "$rna_manifest")"
) > "$case_root/rna_manifest_checksum.sha256"
(
  cd "$(dirname "$chip_manifest")"
  sha256sum "$(basename "$chip_manifest")"
) > "$case_root/chip_manifest_checksum.sha256"
printf 'python=%s\njava=%s\nnextflow_jar_sha256=%s\n' \
  "$($python_runtime/python3 --version 2>&1)" \
  "$($java_bin -version 2>&1 | head -1)" \
  "$(sha256sum "$nextflow_jar" | awk '{print $1}')" > "$case_root/environment.txt"

export PATH="$python_runtime/bin:$PATH"
export NXF_HOME="$nxf_home"
export NXF_CACHE_DIR="$cache"

"$java_bin" -Xms128m -Xmx1g -jar "$nextflow_jar" -log "$logs/nextflow.log" \
  run "$repo_root/main.nf" \
  -profile slurm \
  -c "$repo_root/benchmark/integrative/configs/real_integration_slurm.config" \
  -ansi-log false \
  -work-dir "$work" \
  -with-trace "$logs/trace.tsv" \
  -with-report "$logs/report.html" \
  -with-timeline "$logs/timeline.html" \
  -with-dag "$logs/dag.html" \
  --workflow integrative \
  --outdir "$results" \
  --rna_manifest "$rna_manifest" \
  --chip_manifest "$chip_manifest" \
  --integrative_harmonization_policy "$case_root/frozen_inputs/harmonization_policy.json" \
  --integrative_interpretation_policy "$case_root/frozen_inputs/interpretation_policy.json" \
  --integrative_mark_roles "$case_root/frozen_inputs/mark_roles.tsv" \
  --integrative_prioritization_context "$case_root/frozen_inputs/prioritization_context.tsv" \
  --integrative_functional_annotation "$case_root/frozen_inputs/functional_annotation.tsv" \
  --integrative_report_title "HelixForge GSE133183 real biological integration"

printf 'TECHNICAL_EXECUTION=COMPLETE\n' > "$case_root/execution.status"
