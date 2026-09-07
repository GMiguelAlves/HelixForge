#!/usr/bin/env bash
set -euo pipefail

repo=${1:-/home/CLUSTER_USER/helixforge-integrative-reentry-20260901}
root=${2:-/scratch/HELIXFORGE_WORKSPACE/helixforge-integrative-real-20260901}
mark=${3:?mark is required: H3K27me3 or H3K27ac}
queue=${4:-general}
run_mode=${5:-fresh}
attempt_label=${6:-initial}
case "$mark" in
    H3K27me3)
        case_name=chipseq_h3k27me3
        peak_type=broad
        submitted_phase=CHIPSEQ_H3K27ME3_SUBMITTED
        failed_phase=CHIPSEQ_H3K27ME3_FAILED
        complete_phase=CHIPSEQ_H3K27ME3_COMPLETE
        ;;
    H3K27ac)
        case_name=chipseq_h3k27ac
        peak_type=narrow
        submitted_phase=CHIPSEQ_H3K27AC_SUBMITTED
        failed_phase=CHIPSEQ_H3K27AC_FAILED
        complete_phase=CHIPSEQ_H3K27AC_COMPLETE
        ;;
    *)
        echo "unsupported mark: $mark" >&2
        exit 2
        ;;
esac

case_root="$root/cases/$case_name"
state="$root/benchmark_state.json"
nextflow_jar=/home/CLUSTER_USER/.nextflow/framework/25.10.7/nextflow-25.10.7-one.jar
java_runtime=/scratch/HELIXFORGE_WORKSPACE/helixforge-rnaseq-benchmark-20260825/envs/rna-tools-rc
python_runtime=/scratch/HELIXFORGE_WORKSPACE/helixforge-rnaseq-benchmark-20260825/envs/python-runtime-rc
chip_runtime=/home/CLUSTER_USER/miniconda3/envs/chipseq
resource_config="$repo/benchmark/integrative/configs/real_upstream_slurm.config"
scientific_target=dc0218ce902302da476910595bb133c82fee927c
driver_id="driver-${case_name}-${attempt_label}-${BASHPID}"
repo_commit=$(git -C "$repo" rev-parse HEAD)

update() {
    HF_STATE_TIME_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ) \
        "$python_runtime/bin/python3" "$repo/benchmark/integrative/scripts/real/update_real_benchmark_state.py" \
        --state "$state" --phase "$1" --status "$2" --job-id "$driver_id" \
        --job-kind "${case_name}_nextflow_driver" --repo-commit "$repo_commit" \
        --workdir "$case_root/work" \
        --expected-output "cases/$case_name/results/chipseq/chipseq_run_manifest.json"
}

test -z "${SLURM_JOB_ID:-}"
test -s "$case_root/input_manifest.json"
test -s "$case_root/pipeline_config.sh"
test -s "$case_root/db_spec.json"
test -s "$resource_config"
test -s "$nextflow_jar"
test -x "$java_runtime/bin/java"
for executable in bowtie2 bowtie2-build samtools macs3 bedtools featureCounts Rscript bamCoverage fastqc multiqc; do
    test -x "$chip_runtime/bin/$executable"
done

resume_args=()
if [[ "$run_mode" == fresh ]]; then
    test ! -e "$case_root/results"
    test ! -e "$case_root/work"
elif [[ "$run_mode" == resume ]]; then
    test -d "$case_root/work"
    resume_args=(-resume)
else
    echo "invalid run mode: $run_mode" >&2
    exit 2
fi

git -C "$repo" diff --quiet "$scientific_target" -- \
    main.nf nextflow.config nextflow_schema.json workflows subworkflows modules schemas pipelines
"$java_runtime/bin/java" -jar "$nextflow_jar" -version 2>&1 | grep -Fq 'version 25.10.7'
[[ "$("$chip_runtime/bin/macs3" --version)" == 'macs3 3.0.4' ]]

mkdir -p "$case_root/logs" "$case_root/nxf-home" "$case_root/nxf-cache"
runtime_path="$chip_runtime/bin:$python_runtime/bin:/usr/bin:/bin"
started=$(date -u +%Y-%m-%dT%H:%M:%SZ)
trap 'update "$failed_phase" FAILED' ERR
update "$submitted_phase" RUNNING

cd "$repo"
env PATH="$runtime_path" \
    NXF_HOME="$case_root/nxf-home" \
    NXF_CACHE_DIR="$case_root/nxf-cache" \
    "$java_runtime/bin/java" -Xms128m -Xmx1g -jar "$nextflow_jar" \
    -log "$case_root/logs/nextflow.log" \
    run main.nf \
    "${resume_args[@]}" \
    -c "$resource_config" \
    -ansi-log false \
    -work-dir "$case_root/work" \
    -process.queue="$queue" \
    --workflow chipseq \
    --outdir "$case_root/results" \
    --chipseq_config "$case_root/pipeline_config.sh" \
    --chipseq_run_mode full \
    --chipseq_min_mapq 30 \
    --chipseq_exclude_flags 2308 \
    --chipseq_duplicate_mode none \
    --chipseq_blacklist "$root/reference/bundle/blacklist.bed" \
    --chipseq_blacklist_overlap_mode fragment \
    --chipseq_peak_caller macs3 \
    --chipseq_peak_type "$peak_type" \
    --chipseq_effective_genome_size 2913022398 \
    --chipseq_peak_q_value 0.01 \
    --chipseq_peak_format BAMPE \
    --chipseq_peak_duplicate_policy all \
    --chipseq_peak_output_dir "$case_root/results/080-peak-calling" \
    --chipseq_replicate_mode biological \
    --chipseq_replicate_policy require_premerged \
    --chipseq_consensus_method union \
    --chipseq_min_replicates 2 \
    --chipseq_frip_min_mapq 30 \
    --chipseq_frip_duplicate_handling include \
    --chipseq_frip_blacklist_policy bam_preprocessed \
    --chipseq_db_spec "$case_root/db_spec.json" \
    --chipseq_db_target_dir "$case_root/results/120-differential-binding" \
    --chipseq_track_bin_size 10 \
    --chipseq_track_normalization CPM \
    --chipseq_track_aggregate true \
    --chipseq_report_title "GSE133183 K562 $mark GSK343 versus DMSO" \
    --bowtie2_index_queue "$queue" \
    --bowtie2_align_queue "$queue" \
    --bam_select_queue "$queue" \
    --bam_duplicates_queue "$queue" \
    --bam_blacklist_queue "$queue" \
    --bam_index_qc_queue "$queue" \
    --macs3_queue "$queue" \
    --peak_qc_queue "$queue" \
    --consensus_queue "$queue" \
    --db_count_queue "$queue" \
    --db_model_queue "$queue" \
    --db_contrast_queue "$queue"

manifest="$case_root/results/chipseq/chipseq_run_manifest.json"
test -s "$manifest"
"$python_runtime/bin/python3" - "$manifest" "$mark" "$peak_type" <<'PY'
import json
import sys
from pathlib import Path

manifest = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
mark, peak_type = sys.argv[2:]
if manifest.get("schema_version") != "1.0" or manifest.get("type") != "chipseq_run_manifest":
    raise SystemExit("invalid ChIP-seq terminal manifest")
if manifest.get("status") != "complete":
    raise SystemExit("incomplete ChIP-seq terminal manifest")
artifacts = manifest.get("artifacts", [])
if not any(item.get("artifact_type") == "differential_binding" for item in artifacts):
    raise SystemExit("terminal manifest has no differential-binding artifact")
if not any(item.get("mark_or_factor") == mark or mark in item.get("marks_or_factors", []) for item in artifacts):
    raise SystemExit(f"terminal manifest has no {mark} evidence")
if not any(item.get("peak_type") == peak_type for item in artifacts):
    raise SystemExit(f"terminal manifest has no {peak_type} peak evidence")
PY

ended=$(date -u +%Y-%m-%dT%H:%M:%SZ)
"$python_runtime/bin/python3" - "$case_root/execution_identity.json" "$repo_commit" "$scientific_target" "$started" "$ended" "$queue" "$mark" "$peak_type" "$run_mode" "$attempt_label" <<'PY'
import json
import sys
from pathlib import Path

path, commit, target, started, ended, queue, mark, peak_type, run_mode, attempt = sys.argv[1:]
Path(path).write_text(json.dumps({
    "schema_version": "1.0", "status": "COMPLETE", "workflow": "chipseq",
    "role": "INPUT_GENERATION_FOR_INTEGRATIVE_BENCHMARK",
    "repository_commit": commit, "scientific_target_commit": target,
    "core_equal_to_scientific_target": True, "nextflow": "25.10.7", "java_major": 21,
    "queue": queue, "queue_size": 5, "samples": 8, "mark": mark,
    "peak_type": peak_type, "peak_caller": "macs3", "peak_q_value": 0.01,
    "consensus_method": "union", "design": "~ condition",
    "contrast": "GSK343_vs_DMSO", "run_mode": run_mode, "attempt_label": attempt,
    "started_utc": started, "ended_utc": ended,
}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

update "$complete_phase" COMPLETE
trap - ERR
