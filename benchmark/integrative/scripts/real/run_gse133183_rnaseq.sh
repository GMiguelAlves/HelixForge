#!/usr/bin/env bash
set -euo pipefail

repo=${1:-/home/ra236875@bio.ib.unicamp.br/helixforge-integrative-reentry-20260901}
root=${2:-/scratch/Schisto-epigenetics/gustavo/helixforge-integrative-real-20260901}
queue=${3:-general}
run_mode=${4:-fresh}
case_root="$root/cases/rnaseq"
state="$root/benchmark_state.json"
nextflow_jar=/home/ra236875@bio.ib.unicamp.br/.nextflow/framework/25.10.7/nextflow-25.10.7-one.jar
rna_runtime=/scratch/Schisto-epigenetics/gustavo/helixforge-rnaseq-benchmark-20260825/envs/rna-tools-rc
python_runtime=/scratch/Schisto-epigenetics/gustavo/helixforge-rnaseq-benchmark-20260825/envs/python-runtime-rc
r_runtime=/scratch/Schisto-epigenetics/gustavo/helixforge-rnaseq-benchmark-20260825/envs/r-analysis-rc
resource_config="$repo/benchmark/integrative/configs/real_upstream_slurm.config"
scientific_target=dc0218ce902302da476910595bb133c82fee927c
driver_id="driver-rnaseq-${BASHPID}"
repo_commit=$(git -C "$repo" rev-parse HEAD)

update() {
    HF_STATE_TIME_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ) \
        python3 "$repo/benchmark/integrative/scripts/real/update_real_benchmark_state.py" \
        --state "$state" --phase "$1" --status "$2" --job-id "$driver_id" \
        --job-kind rnaseq_nextflow_driver --repo-commit "$repo_commit" \
        --workdir "$case_root/work" \
        --expected-output cases/rnaseq/results/rnaseq/rnaseq_run_manifest.json
}

test -z "${SLURM_JOB_ID:-}"
test -s "$case_root/input_manifest.json"
test -s "$case_root/pipeline_config.sh"
test -s "$case_root/analysis_spec.json"
test -s "$case_root/report_genes.txt"
test -s "$resource_config"
test -s "$nextflow_jar"
test -x "$rna_runtime/bin/java"
test -x "$rna_runtime/bin/salmon"
test -x "$python_runtime/bin/python3"
test -x "$r_runtime/bin/Rscript"
resume_args=()
if [[ "$run_mode" == fresh ]]; then
    test ! -e "$case_root/results"
    test ! -e "$case_root/work"
elif [[ "$run_mode" == resume ]]; then
    test -d "$case_root/work"
    test ! -e "$case_root/execution_identity.json"
    resume_args=(-resume)
else
    echo "invalid run mode: $run_mode" >&2
    exit 2
fi
git -C "$repo" diff --quiet "$scientific_target" -- \
    main.nf nextflow.config nextflow_schema.json workflows subworkflows modules schemas pipelines
"$rna_runtime/bin/java" -jar "$nextflow_jar" -version 2>&1 | grep -Fq 'version 25.10.7'

mkdir -p "$case_root/logs" "$case_root/nxf-home" "$case_root/nxf-cache"
runtime_path="$python_runtime/bin:$r_runtime/bin:$rna_runtime/bin:/usr/bin:/bin"
started=$(date -u +%Y-%m-%dT%H:%M:%SZ)
if [[ "$run_mode" == resume ]]; then
    submitted_phase=RNASEQ_RETRY_SUBMITTED
    failed_phase=RNASEQ_RETRY_FAILED
    complete_phase=RNASEQ_RETRY_COMPLETE
else
    submitted_phase=RNASEQ_SUBMITTED
    failed_phase=RNASEQ_FAILED
    complete_phase=RNASEQ_COMPLETE
fi
trap 'update "$failed_phase" FAILED' ERR
update "$submitted_phase" RUNNING

cd "$repo"
env PATH="$runtime_path" \
    FONTCONFIG_PATH="$rna_runtime/etc/fonts" \
    FONTCONFIG_FILE="$rna_runtime/etc/fonts/fonts.conf" \
    XDG_DATA_DIRS="$rna_runtime/share:/usr/local/share:/usr/share" \
    NXF_HOME="$case_root/nxf-home" \
    NXF_CACHE_DIR="$case_root/nxf-cache" \
    "$rna_runtime/bin/java" -Xms128m -Xmx1g -jar "$nextflow_jar" \
    -log "$case_root/logs/nextflow.log" \
    run main.nf \
    "${resume_args[@]}" \
    -c "$resource_config" \
    -ansi-log false \
    -work-dir "$case_root/work" \
    -process.queue="$queue" \
    --workflow rnaseq \
    --outdir "$case_root/results" \
    --rnaseq_config "$case_root/pipeline_config.sh" \
    --rnaseq_analysis_mode quantification \
    --rnaseq_run_mode full \
    --rnaseq_native_alignment false \
    --rnaseq_native_quantification true \
    --rnaseq_native_import true \
    --rnaseq_native_de true \
    --rnaseq_import_policy production_v1 \
    --rnaseq_de_spec "$case_root/analysis_spec.json" \
    --rnaseq_library_protocol full_length \
    --rnaseq_counts_from_abundance lengthScaledTPM \
    --rnaseq_report_enabled true \
    --rnaseq_report_genes "$case_root/report_genes.txt" \
    --rnaseq_report_title 'GSE133183 K562 GSK343 versus DMSO' \
    --salmon_validate_mappings true \
    --salmon_index_queue "$queue" \
    --salmon_quant_queue "$queue" \
    --tx2gene_queue "$queue" \
    --tximport_queue "$queue" \
    --deseq2_model_queue "$queue" \
    --deseq2_contrast_queue "$queue" \
    --rnaseq_report_queue "$queue"

manifest="$case_root/results/rnaseq/rnaseq_run_manifest.json"
test -s "$manifest"
"$python_runtime/bin/python3" - "$manifest" <<'PY'
import json
import sys
from pathlib import Path

manifest = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if manifest.get("schema_version") != "1.0" or manifest.get("type") != "rnaseq_run_manifest":
    raise SystemExit("invalid RNA-seq terminal manifest")
if manifest.get("quantification_method") != "salmon":
    raise SystemExit("terminal manifest does not declare Salmon")
PY

ended=$(date -u +%Y-%m-%dT%H:%M:%SZ)
"$python_runtime/bin/python3" - "$case_root/execution_identity.json" "$repo_commit" "$scientific_target" "$started" "$ended" "$queue" "$run_mode" <<'PY'
import json
import sys
from pathlib import Path

path, commit, target, started, ended, queue, run_mode = sys.argv[1:]
Path(path).write_text(json.dumps({
    "schema_version": "1.0", "status": "COMPLETE", "workflow": "rnaseq",
    "role": "INPUT_GENERATION_FOR_INTEGRATIVE_BENCHMARK",
    "repository_commit": commit, "scientific_target_commit": target,
    "core_equal_to_scientific_target": True, "nextflow": "25.10.7", "java_major": 21,
    "queue": queue, "queue_size": 5, "samples": 4,
    "quantification_provider": "salmon", "design": "~ condition",
    "contrast": "condition__GSK343_vs_DMSO", "run_mode": run_mode,
    "started_utc": started, "ended_utc": ended,
}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
update "$complete_phase" COMPLETE
trap - ERR
