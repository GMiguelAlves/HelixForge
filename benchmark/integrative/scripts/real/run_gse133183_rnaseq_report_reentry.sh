#!/usr/bin/env bash
set -euo pipefail

repo=${1:-/home/ra236875@bio.ib.unicamp.br/helixforge-integrative-post-qc-20260902}
root=${2:-/scratch/Schisto-epigenetics/gustavo/helixforge-integrative-real-20260901}
queue=${3:-general}
case_root="$root/cases/rnaseq"
state="$root/benchmark_state.json"
nextflow_jar=/home/ra236875@bio.ib.unicamp.br/.nextflow/framework/25.10.7/nextflow-25.10.7-one.jar
rna_runtime=/scratch/Schisto-epigenetics/gustavo/helixforge-rnaseq-benchmark-20260825/envs/rna-tools-rc
python_runtime=/scratch/Schisto-epigenetics/gustavo/helixforge-rnaseq-benchmark-20260825/envs/python-runtime-rc
r_runtime=/scratch/Schisto-epigenetics/gustavo/helixforge-rnaseq-benchmark-20260825/envs/r-analysis-rc
resource_config="$repo/benchmark/integrative/configs/real_upstream_slurm.config"
entrypoint="$repo/benchmark/integrative/workflows/gse133183_rnaseq_report_reentry.nf"
driver_id="driver-rnaseq-report-reentry-${BASHPID}"
repo_commit=$(git -C "$repo" rev-parse HEAD)
scientific_target=dc0218ce902302da476910595bb133c82fee927c

update() {
    HF_STATE_TIME_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ) \
        python3 "$repo/benchmark/integrative/scripts/real/update_real_benchmark_state.py" \
        --state "$state" --phase "$1" --status "$2" --job-id "$driver_id" \
        --job-kind rnaseq_report_reentry_driver --repo-commit "$repo_commit" \
        --workdir "$case_root/report_reentry_work" \
        --expected-output cases/rnaseq/results/rnaseq/rnaseq_run_manifest.json
}

test -z "${SLURM_JOB_ID:-}"
test -s "$entrypoint"
test -s "$case_root/reference_bundle.normalized.manifest.json"
test -s "$case_root/results/pipeline_info/native_import/tximport/import_manifest.json"
test -s "$case_root/results/pipeline_info/native_de/aggregate/de_manifest.json"
test -s "$case_root/results/pipeline_info/native_de/aggregate/DEGs_all_results.tsv"
test -s "$case_root/results/pipeline_info/native_de/aggregate/normalized_counts_condition.tsv"
git -C "$repo" diff --quiet "$scientific_target" -- \
    main.nf nextflow.config nextflow_schema.json workflows subworkflows modules schemas pipelines

# Correct only the benchmark input serialization. The candidate set itself is
# unchanged and the original invalid content is retained in the audit record.
"$python_runtime/bin/python3" - "$case_root/report_genes.txt" "$case_root/report_genes_correction.json" <<'PY'
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

path, audit_path = map(Path, sys.argv[1:])
before = path.read_bytes()
expected = b"FGF18\nUBTD2\nFBXW11\nIGF2\nHBB\nHBZ\nHBE1\n"
corrected = b"GSE133183_candidates: FGF18, UBTD2, FBXW11, IGF2, HBB, HBZ, HBE1\n"
if before not in (expected, corrected):
    raise SystemExit("unexpected candidate-gene content; refusing automatic correction")
path.write_bytes(corrected)
audit = {
    "schema_version": "1.0", "status": "COMPLETE",
    "type": "benchmark_input_contract_correction",
    "field": "report_genes", "scientific_values_changed": False,
    "reason": "candidate_genes_v1 requires group: gene1, gene2 serialization",
    "before_sha256": hashlib.sha256(before).hexdigest(),
    "after_sha256": hashlib.sha256(corrected).hexdigest(),
    "genes": ["FGF18", "UBTD2", "FBXW11", "IGF2", "HBB", "HBZ", "HBE1"],
}
audit_path.parent.mkdir(parents=True, exist_ok=True)
with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=audit_path.parent, delete=False) as handle:
    json.dump(audit, handle, indent=2, sort_keys=True)
    handle.write("\n")
    temporary = Path(handle.name)
os.replace(temporary, audit_path)
PY

mkdir -p "$case_root/logs/report_reentry" "$case_root/report_reentry_nxf_home" "$case_root/report_reentry_nxf_cache"
runtime_path="$python_runtime/bin:$r_runtime/bin:$rna_runtime/bin:/usr/bin:/bin"
started=$(date -u +%Y-%m-%dT%H:%M:%SZ)
trap 'update RNASEQ_REPORT_REENTRY_FAILED FAILED' ERR
update RNASEQ_REPORT_REENTRY_SUBMITTED RUNNING

cd "$repo"
env PATH="$runtime_path" \
    FONTCONFIG_PATH="$rna_runtime/etc/fonts" \
    FONTCONFIG_FILE="$rna_runtime/etc/fonts/fonts.conf" \
    XDG_DATA_DIRS="$rna_runtime/share:/usr/local/share:/usr/share" \
    NXF_HOME="$case_root/report_reentry_nxf_home" \
    NXF_CACHE_DIR="$case_root/report_reentry_nxf_cache" \
    "$rna_runtime/bin/java" -Xms128m -Xmx1g -jar "$nextflow_jar" \
    -log "$case_root/logs/report_reentry/nextflow.log" \
    run "$entrypoint" \
    -c "$resource_config" -ansi-log false \
    -work-dir "$case_root/report_reentry_work" -process.queue="$queue" \
    --helixforge_root "$repo" --case_root "$case_root" --outdir "$case_root/results" \
    --precomputed_annotation "$root/reference/bundle/annotation.gtf" \
    --rnaseq_de_spec "$case_root/analysis_spec.json" \
    --rnaseq_report_outdir "$case_root/pipeline/090-search-gene" \
    --rnaseq_report_title 'GSE133183 K562 GSK343 versus DMSO' \
    --rnaseq_report_queue "$queue"

if grep -Eq 'Submitted process > .*:(RNASEQ_QC|SALMON_|TX2GENE_|SALMON_IMPORT|DESEQ2_)' \
    "$case_root/logs/report_reentry/driver.out"; then
    echo 'report re-entry unexpectedly submitted an upstream scientific process' >&2
    exit 3
fi

manifest="$case_root/results/rnaseq/rnaseq_run_manifest.json"
test -s "$manifest"
test -s "$case_root/pipeline/090-search-gene/results/gene_set_report.html"
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
    "core_equal_to_scientific_target": True, "nextflow": "25.10.7", "java_major": 21,
    "queue": queue, "queue_size": 5, "samples": 4,
    "quantification_provider": "salmon", "design": "~ condition",
    "contrast": "condition__GSK343_vs_DMSO", "qc_recomputed": False,
    "heavy_session": "irreverent_curran", "terminal_manifest_session": "report_reentry",
    "reentry_boundaries": ["post_qc", "post_deseq2"],
    "started_utc": started, "ended_utc": ended,
}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
update RNASEQ_REPORT_REENTRY_COMPLETE COMPLETE
trap - ERR
