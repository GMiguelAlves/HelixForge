#!/usr/bin/env bash

set -euo pipefail

if [[ "$#" -ne 6 ]]; then
    echo "Usage: run_legacy_step.sh PIPELINE STEP LEGACY_ROOT CONFIG LOG DONE" >&2
    exit 2
fi

pipeline="$1"
step="$2"
legacy_root="$3"
config_file="$4"
log_file="$5"
done_file="$6"

[[ -d "$legacy_root" ]] || { echo "Legacy root not found: $legacy_root" >&2; exit 2; }
[[ -f "$config_file" ]] || { echo "Legacy config not found: $config_file" >&2; exit 2; }

case "$pipeline" in
    rnaseq)
        orchestrator="${legacy_root}/rnaseq_pipeline.sh"
        command=(bash "$orchestrator" --config "$config_file" --step "$step" --local)
        ;;
    chipseq)
        orchestrator="${legacy_root}/chipseq_pipeline.sh"
        command=(bash "$orchestrator" --config "$config_file" --step "$step" --local)
        ;;
    integrative)
        orchestrator="${legacy_root}/integrative_pipeline.sh"
        command=(bash "$orchestrator" --config "$config_file" --step "$step" --mode local)
        ;;
    *)
        echo "Unsupported legacy pipeline: $pipeline" >&2
        exit 2
        ;;
esac

[[ -f "$orchestrator" ]] || { echo "Legacy orchestrator not found: $orchestrator" >&2; exit 2; }

optional_enabled=true
if [[ "$pipeline" == "rnaseq" && "$step" == "batch" ]]; then
    optional_enabled="$({ PROJECT_DIR="$legacy_root" PIPELINE_EXECUTOR=local bash -c 'source "$1"; [[ "${RUN_BATCH_CORRECTION:-0}" == "1" ]] && echo true || echo false' _ "$config_file"; })"
elif [[ "$pipeline" == "rnaseq" && "$step" == "report" ]]; then
    optional_enabled="$({ PROJECT_DIR="$legacy_root" PIPELINE_EXECUTOR=local bash -c 'source "$1"; [[ "${RUN_GENE_REPORT:-0}" == "1" ]] && echo true || echo false' _ "$config_file"; })"
fi

if [[ "$optional_enabled" != "true" ]]; then
    printf '[SKIP] Optional legacy step disabled by pipeline_config.sh: %s/%s\n' "$pipeline" "$step" | tee "$log_file"
else
    printf '[INFO] OmicsFlow compatibility step: %s/%s\n' "$pipeline" "$step" | tee "$log_file"
    printf '[INFO] Legacy root: %s\n' "$legacy_root" | tee -a "$log_file"
    printf '[INFO] Config: %s\n' "$config_file" | tee -a "$log_file"

    export PROJECT_DIR="$legacy_root"
    export PIPELINE_CONFIG="$config_file"
    export PIPELINE_EXECUTOR=local
    export RUN_MODE=local
    export SKIP_SLURM_CHECK=true

    set +e
    "${command[@]}" 2>&1 | tee -a "$log_file"
    command_status=${PIPESTATUS[0]}
    set -e
    [[ "$command_status" -eq 0 ]] || exit "$command_status"
fi

printf '{"pipeline":"%s","step":"%s","status":"complete","scheduler":"nextflow"}\n' \
    "$pipeline" "$step" > "$done_file"

