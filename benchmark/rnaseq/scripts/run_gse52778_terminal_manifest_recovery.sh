#!/usr/bin/env bash
set -euo pipefail

repo_root=${1:?benchmark checkout is required}
nextflow_jar=${2:?Nextflow jar is required}
java_bin=${3:?Java 21 executable is required}
python_env=${4:?certified Python prefix is required}
case_root=${5:?prepared case root is required}
recovery_spec=${6:?terminal recovery specification is required}
expected_commit=${7:?validated hotfix commit is required}
queue=${8:-general}

test -z "${SLURM_JOB_ID:-}"
test -x "$java_bin"
test -s "$nextflow_jar"
test -x "$python_env/bin/python3"
test -s "$recovery_spec"
test ! -e "$case_root/results/rnaseq/rnaseq_run_manifest.json"
[[ "$(git -C "$repo_root" rev-parse HEAD)" == "$expected_commit" ]]
git -C "$repo_root" diff --quiet v1.0.0-rc.1 -- \
    modules/local/run_manifest \
    bin/build_run_manifest.py \
    bin/integration_contract.py \
    bin/validate_integration_manifest.py \
    schemas/integration

recovery="$case_root/terminal-manifest-recovery"
mkdir -p "$recovery/logs" "$recovery/nxf-home" "$recovery/nxf-cache"
runtime_path="$repo_root/bin:$python_env/bin:$(dirname "$java_bin"):/usr/bin:/bin"
started=$(date -u +%Y-%m-%dT%H:%M:%SZ)

cd "$repo_root"
env PATH="$runtime_path" \
    NXF_HOME="$recovery/nxf-home" \
    NXF_CACHE_DIR="$recovery/nxf-cache" \
    "$java_bin" -Xms128m -Xmx1g -jar "$nextflow_jar" \
    -log "$recovery/logs/nextflow.log" \
    run benchmark/rnaseq/workflows/gse52778_terminal_manifest_recovery.nf \
    -c benchmark/rnaseq/configs/slurm-biological.config \
    -ansi-log false \
    -work-dir "$recovery/work" \
    -process.queue="$queue" \
    --outdir "$case_root/results" \
    --recovery_spec "$recovery_spec" \
    --schema_root "$repo_root/schemas/integration"

ended=$(date -u +%Y-%m-%dT%H:%M:%SZ)
printf '{"status":"complete","type":"terminal_manifest_recovery","base_rc_tag":"v1.0.0-rc.1","run_manifest_code_equal_rc":true,"validated_commit":"%s","nextflow":"25.10.7","java_major":21,"started_utc":"%s","ended_utc":"%s","queue":"%s"}\n' \
    "$expected_commit" "$started" "$ended" "$queue" > "$recovery/recovery_identity.json"
