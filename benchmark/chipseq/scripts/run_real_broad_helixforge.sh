#!/usr/bin/env bash
set -euo pipefail

repo_root=${1:?repository root is required}
benchmark_root=${2:?benchmark root is required}
runtime_prefix=${3:?frozen ChIP runtime prefix is required}
java_home=${4:?Java 21 home is required}
nextflow_launcher=${5:?Nextflow launcher is required}
queue=${6:-general}
mode=${7:-run}

scientific_target=0829c7c154dc634ffd4e13672b95ad4fbdc5957f
protocol_commit=bb8db940ee137fee67fe5f13530521326c96dfc0
expected_root=/scratch/Schisto-epigenetics/gustavo/helixforge-chipseq-real-broad-benchmark-20260830
run_root="$benchmark_root/helixforge"
result_root="$run_root/results"
work_root="$benchmark_root/work/helixforge"
cache_root="$benchmark_root/cache/helixforge"
log_root="$run_root/logs"

[[ -z "${SLURM_JOB_ID:-}" ]] || { echo "The Nextflow driver must run on the head node." >&2; exit 2; }
[[ "$(realpath -m "$benchmark_root")" == "$expected_root" ]]
[[ "$(git -C "$repo_root" rev-parse "$scientific_target")" == "$scientific_target" ]]
git -C "$repo_root" diff --quiet "$scientific_target" -- \
    main.nf nextflow.config nextflow_schema.json workflows subworkflows modules schemas pipelines
[[ "$(git -C "$repo_root" merge-base HEAD "$protocol_commit")" == "$protocol_commit" ]]
[[ -x "$runtime_prefix/bin/bowtie2" && -x "$runtime_prefix/bin/samtools" && -x "$runtime_prefix/bin/macs3" ]]
[[ -x "$java_home/bin/java" && -x "$nextflow_launcher" ]]
[[ -s "$benchmark_root/preflight/environment.json" ]]
[[ -s "$benchmark_root/downloads/provenance/download_manifest.json" ]]
[[ -s "$benchmark_root/reference/reference_manifest.json" ]]

export JAVA_HOME="$java_home"
export PATH="$runtime_prefix/bin:$java_home/bin:/usr/bin:/bin"
export NXF_VER=25.10.7
export NXF_HOME="$benchmark_root/runtime/nxf-home-25.10.7"
export NXF_CACHE_DIR="$cache_root"

[[ "$($nextflow_launcher -version 2>&1)" == *"version 25.10.7"* ]]
[[ "$(bowtie2 --version | head -n 1)" == *"version 2.5.4"* ]]
[[ "$(samtools --version | head -n 1)" == "samtools 1.20" ]]
[[ "$(macs3 --version)" == "macs3 3.0.4" ]]

resume_args=()
if [[ "$mode" == resume ]]; then
    [[ -d "$run_root" ]]
    resume_args=(-resume)
elif [[ "$mode" == run ]]; then
    [[ ! -e "$run_root" ]] || { echo "Refusing existing run root: $run_root" >&2; exit 4; }
    mkdir -p "$run_root" "$log_root" "$cache_root" "$work_root"
    "$runtime_prefix/bin/python" "$repo_root/benchmark/chipseq/scripts/prepare_helixforge_real_broad_inputs.py" \
        --benchmark-root "$benchmark_root" --run-root "$run_root/input"
else
    echo "Mode must be run or resume" >&2
    exit 2
fi

command=(
    "$nextflow_launcher" -log "$log_root/nextflow.log"
    run "$repo_root/main.nf" "${resume_args[@]}"
    -c "$repo_root/benchmark/chipseq/configs/benchmark-slurm.config"
    -ansi-log false -work-dir "$work_root" -process.queue="$queue"
    --workflow chipseq --outdir "$result_root"
    --chipseq_config "$run_root/input/pipeline_config.sh"
    --chipseq_run_mode consensus
    --chipseq_min_mapq 30 --chipseq_exclude_flags 2308
    --chipseq_duplicate_mode none
    --chipseq_blacklist "$benchmark_root/reference/blacklist.bed"
    --chipseq_blacklist_overlap_mode fragment
    --chipseq_peak_caller macs3 --chipseq_peak_type broad
    --chipseq_effective_genome_size 2913022398
    --chipseq_peak_q_value 0.01 --chipseq_peak_format BAM
    --chipseq_peak_duplicate_policy all
    --chipseq_peak_output_dir "$result_root/080-peak-calling"
    --chipseq_replicate_mode biological --chipseq_replicate_policy require_premerged
    --chipseq_consensus_method replicate_support --chipseq_min_replicates 2
    --chipseq_frip_min_mapq 30 --chipseq_frip_duplicate_handling include
    --chipseq_frip_blacklist_policy bam_preprocessed
    --bowtie2_index_queue "$queue" --bowtie2_align_queue "$queue"
    --bam_select_queue "$queue" --bam_duplicates_queue "$queue"
    --bam_blacklist_queue "$queue" --bam_index_qc_queue "$queue"
    --macs3_queue "$queue" --peak_qc_queue "$queue" --consensus_queue "$queue"
    -with-trace "$run_root/trace.tsv"
    -with-report "$run_root/report.html"
    -with-timeline "$run_root/timeline.html"
    -with-dag "$run_root/dag.html"
)

printf '%q ' "${command[@]}" > "$log_root/nextflow.command.sh"
printf '\n' >> "$log_root/nextflow.command.sh"
printf '%s\n' "$scientific_target" > "$run_root/scientific_target.txt"
printf '%s\n' "$protocol_commit" > "$run_root/protocol_commit.txt"
printf '%s\n' "$(git -C "$repo_root" rev-parse HEAD)" > "$run_root/benchmark_commit.txt"
"${command[@]}"
