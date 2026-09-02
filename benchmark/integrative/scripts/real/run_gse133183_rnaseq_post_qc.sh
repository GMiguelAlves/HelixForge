#!/usr/bin/env bash
set -euo pipefail

repo=${1:-/home/ra236875@bio.ib.unicamp.br/helixforge-integrative-reentry-20260901}
root=${2:-/scratch/Schisto-epigenetics/gustavo/helixforge-integrative-real-20260901}
queue=${3:-general}
case_root="$root/cases/rnaseq"
state="$root/benchmark_state.json"
nextflow_jar=/home/ra236875@bio.ib.unicamp.br/.nextflow/framework/25.10.7/nextflow-25.10.7-one.jar
rna_runtime=/scratch/Schisto-epigenetics/gustavo/helixforge-rnaseq-benchmark-20260825/envs/rna-tools-rc
python_runtime=/scratch/Schisto-epigenetics/gustavo/helixforge-rnaseq-benchmark-20260825/envs/python-runtime-rc
r_runtime=/scratch/Schisto-epigenetics/gustavo/helixforge-rnaseq-benchmark-20260825/envs/r-analysis-rc
resource_config="$repo/benchmark/integrative/configs/real_upstream_slurm.config"
entrypoint="$repo/benchmark/integrative/workflows/gse133183_rnaseq_post_qc.nf"
qc_plan="$case_root/results/pipeline_info/native_rnaseq/metadata/gse133183_k562_qc_plan.csv"
metadata="$case_root/results/pipeline_info/native_rnaseq/metadata/validated_metadata.csv"
qc_status="$case_root/results/pipeline_info/native_qc/multiqc/gse133183_k562.multiqc.multiqc.done"
annotation="$root/reference/bundle/annotation.gtf"
reference_manifest_base="$case_root/results/references/GRCh38.p14_GENCODE_50/reference_bundle.manifest.json"
normalization_manifest="$root/reference/transcriptome_normalization.json"
reference_manifest="$case_root/reference_bundle.normalized.manifest.json"
driver_id="driver-rnaseq-post-qc-${BASHPID}"
repo_commit=$(git -C "$repo" rev-parse HEAD)
scientific_target=dc0218ce902302da476910595bb133c82fee927c

update() {
    HF_STATE_TIME_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ) \
        python3 "$repo/benchmark/integrative/scripts/real/update_real_benchmark_state.py" \
        --state "$state" --phase "$1" --status "$2" --job-id "$driver_id" \
        --job-kind rnaseq_post_qc_nextflow_driver --repo-commit "$repo_commit" \
        --workdir "$case_root/post_qc_work" \
        --expected-output cases/rnaseq/results/rnaseq/rnaseq_run_manifest.json
}

test -z "${SLURM_JOB_ID:-}"
test -s "$entrypoint"
test -s "$case_root/pipeline_config.sh"
test -s "$case_root/analysis_spec.json"
test -s "$case_root/report_genes.txt"
test -s "$qc_plan"
test -s "$metadata"
test -s "$qc_status"
test -s "$annotation"
test -s "$reference_manifest_base"
test -s "$normalization_manifest"
test -s "$nextflow_jar"
test -x "$rna_runtime/bin/java"
test -x "$rna_runtime/bin/salmon"
test -x "$python_runtime/bin/python3"
test -x "$r_runtime/bin/Rscript"
git -C "$repo" diff --quiet "$scientific_target" -- \
    main.nf nextflow.config nextflow_schema.json workflows subworkflows modules schemas pipelines

# The published QC plan is the audited re-entry boundary. Every merged FASTQ
# declared by it must still exist before any downstream process is submitted.
"$python_runtime/bin/python3" - "$qc_plan" <<'PY'
import csv
import sys
from pathlib import Path

rows = list(csv.DictReader(Path(sys.argv[1]).open(newline="", encoding="utf-8")))
if not rows:
    raise SystemExit("empty precomputed QC plan")
for row in rows:
    for column in ("merged_sample_r1", "merged_sample_r2"):
        path = Path(row[column])
        if not path.is_file() or path.stat().st_size == 0:
            raise SystemExit(f"missing post-QC artifact: {path}")
PY

# Preserve the originally published bundle and derive an auditable terminal
# manifest whose transcriptome checksum reflects the pre-import normalization.
"$python_runtime/bin/python3" - "$reference_manifest_base" "$normalization_manifest" "$reference_manifest" <<'PY'
import json
import os
import sys
import tempfile
from pathlib import Path

base_path, correction_path, output_path = map(Path, sys.argv[1:])
bundle = json.loads(base_path.read_text(encoding="utf-8"))
correction = json.loads(correction_path.read_text(encoding="utf-8"))
transcriptome = next(item for item in bundle["artifacts"] if item["role"] == "transcriptome")
if transcriptome["sha256"] != correction["original_derived_sha256"]:
    raise SystemExit("published bundle does not match the normalized transcriptome provenance")
transcriptome["sha256"] = correction["normalized_sha256"]
transcriptome["size"] = correction["artifact"]["size_bytes"]
bundle["normalization"] = {
    "type": correction["type"],
    "manifest": str(correction_path),
    "repository_commit": correction["repository_commit"],
    "slurm_job_id": correction["slurm_job_id"],
    "header_policy": correction["header_policy"],
    "filter_policy": correction["filter_policy"],
}
output_path.parent.mkdir(parents=True, exist_ok=True)
with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=output_path.parent, delete=False) as handle:
    json.dump(bundle, handle, indent=2, sort_keys=True)
    handle.write("\n")
    temporary = Path(handle.name)
os.replace(temporary, output_path)
PY
test -s "$reference_manifest"

mkdir -p "$case_root/logs/post_qc" "$case_root/post_qc_nxf_home" "$case_root/post_qc_nxf_cache"
runtime_path="$python_runtime/bin:$r_runtime/bin:$rna_runtime/bin:/usr/bin:/bin"
started=$(date -u +%Y-%m-%dT%H:%M:%SZ)
trap 'update RNASEQ_POST_QC_FAILED FAILED' ERR
update RNASEQ_POST_QC_SUBMITTED RUNNING

cd "$repo"
env PATH="$runtime_path" \
    FONTCONFIG_PATH="$rna_runtime/etc/fonts" \
    FONTCONFIG_FILE="$rna_runtime/etc/fonts/fonts.conf" \
    XDG_DATA_DIRS="$rna_runtime/share:/usr/local/share:/usr/share" \
    NXF_HOME="$case_root/post_qc_nxf_home" \
    NXF_CACHE_DIR="$case_root/post_qc_nxf_cache" \
    "$rna_runtime/bin/java" -Xms128m -Xmx1g -jar "$nextflow_jar" \
    -log "$case_root/logs/post_qc/nextflow.log" \
    run "$entrypoint" \
    -c "$resource_config" \
    -ansi-log false \
    -work-dir "$case_root/post_qc_work" \
    -process.queue="$queue" \
    --helixforge_root "$repo" \
    --outdir "$case_root/results" \
    --rnaseq_config "$case_root/pipeline_config.sh" \
    --precomputed_qc_plan "$qc_plan" \
    --precomputed_metadata "$metadata" \
    --precomputed_annotation "$annotation" \
    --precomputed_reference_manifest "$reference_manifest" \
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

# This run is invalid if the benchmark-only entrypoint ever reaches native QC.
if grep -Eq 'FASTQC|TRIM_GALORE|MERGE_FASTQ|MULTIQC' "$case_root/logs/post_qc/nextflow.log"; then
    echo 'post-QC re-entry unexpectedly referenced a QC process' >&2
    exit 3
fi

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
"$python_runtime/bin/python3" - "$case_root/post_qc_execution_identity.json" "$repo_commit" "$scientific_target" "$started" "$ended" "$queue" <<'PY'
import json
import sys
from pathlib import Path

path, commit, target, started, ended, queue = sys.argv[1:]
Path(path).write_text(json.dumps({
    "schema_version": "1.0", "status": "COMPLETE", "workflow": "rnaseq",
    "role": "INPUT_GENERATION_FOR_INTEGRATIVE_BENCHMARK",
    "repository_commit": commit, "scientific_target_commit": target,
    "core_equal_to_scientific_target": True,
    "nextflow": "25.10.7", "java_major": 21,
    "queue": queue, "queue_size": 5, "samples": 4,
    "quantification_provider": "salmon", "design": "~ condition",
    "contrast": "condition__GSK343_vs_DMSO",
    "reentry_boundary": "post_qc",
    "reentry_reason": "Nextflow task-cache entries were unavailable on the shared NFS runtime",
    "qc_recomputed": False,
    "started_utc": started, "ended_utc": ended,
}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
update RNASEQ_POST_QC_COMPLETE COMPLETE
trap - ERR
