#!/usr/bin/env bash

set -euo pipefail

repo_root=${1:?repository root is required}
benchmark_root=${2:?benchmark root is required}
runtime_prefix=${3:?frozen ChIP runtime prefix is required}
chips_binary=${4:?ChIPs v2.4 binary is required}
chips_source_sha256=${5:?ChIPs source SHA-256 is required}
java_home=${6:?Java 21 home is required}
nextflow_launcher=${7:?Nextflow launcher is required}
queue=${8:-general}
mode=${9:-run}

design="$repo_root/benchmark/chipseq/configs/narrow_design.json"
dataset_root="$benchmark_root/dataset"
run_root="$benchmark_root/dataset-generation"
work_root="$benchmark_root/work/dataset-generation"
log_root="$run_root/logs"
observer_id=$(date -u +%Y%m%dT%H%M%SZ)

[[ -z "${SLURM_JOB_ID:-}" ]] || {
    echo "The Nextflow driver must run on the head node." >&2
    exit 2
}
[[ -x "$chips_binary" ]]
[[ -x "$runtime_prefix/bin/bowtie2" ]]
[[ -x "$java_home/bin/java" ]]
[[ -x "$nextflow_launcher" ]]

export JAVA_HOME="$java_home"
export PATH="$runtime_prefix/bin:$java_home/bin:/usr/bin:/bin"
export NXF_VER=25.10.7
export NXF_HOME="$benchmark_root/runtime/nxf-home-25.10.7"
export NXF_CACHE_DIR="$benchmark_root/cache/dataset-generation"

[[ "$($nextflow_launcher -version 2>&1)" == *"version 25.10.7"* ]]
[[ "$(bowtie2 --version | head -n 1)" == *"version 2.5.4"* ]]

resume_args=()
if [[ "$mode" == "resume" ]]; then
    [[ -d "$run_root" ]]
    resume_args=(-resume)
elif [[ "$mode" == "run" ]]; then
    [[ ! -e "$run_root" && ! -e "$dataset_root" ]] || {
        echo "Refusing to overwrite an existing dataset run." >&2
        exit 3
    }
    mkdir -p "$run_root" "$log_root" "$work_root" "$NXF_CACHE_DIR"
else
    echo "Mode must be run or resume" >&2
    exit 2
fi

command=(
    "$nextflow_launcher" -log "$log_root/nextflow.log"
    run "$repo_root/benchmark/chipseq/scripts/synthetic_narrow_dataset.nf"
    "${resume_args[@]}"
    -c "$repo_root/benchmark/chipseq/configs/benchmark-slurm.config"
    -ansi-log false
    -work-dir "$work_root"
    -process.queue="$queue"
    --design_config "$design"
    --chips_binary "$chips_binary"
    --chips_source_sha256 "$chips_source_sha256"
    --dataset_outdir "$dataset_root"
    -with-trace "$run_root/trace.${observer_id}.tsv"
    -with-report "$run_root/report.${observer_id}.html"
    -with-timeline "$run_root/timeline.${observer_id}.html"
    -with-dag "$run_root/dag.${observer_id}.html"
)
printf '%q ' "${command[@]}" > "$log_root/nextflow.command.sh"
printf '\n' >> "$log_root/nextflow.command.sh"
"${command[@]}"
