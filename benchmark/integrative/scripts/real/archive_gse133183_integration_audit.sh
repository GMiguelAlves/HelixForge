#!/usr/bin/env bash
set -euo pipefail

if [[ "$#" -ne 4 ]]; then
  echo "Usage: $0 REPO_ROOT BENCHMARK_ROOT AUDIT_ROOT ARCHIVE_NAME" >&2
  exit 2
fi

repo_root="$1"
benchmark_root="$2"
audit_root="$3"
archive_name="$4"
case_root="$benchmark_root/cases/integration"
prepared="$benchmark_root/prepared_terminal_manifests"
stage="$audit_root/.${archive_name}.staging"
archive="$audit_root/${archive_name}.zip"

[[ -z "${SLURM_JOB_ID:-}" ]] || { echo "Audit packaging runs on the management node" >&2; exit 2; }
[[ "$archive_name" =~ ^helixforge-integrative-gse133183-real-[0-9]{8}$ ]] || {
  echo "Unexpected archive name" >&2
  exit 2
}
[[ "$(basename "$benchmark_root")" == helixforge-integrative-real-* ]] || {
  echo "Unexpected benchmark root" >&2
  exit 2
}
[[ "$(basename "$audit_root")" == "helixforge-audits" ]] || {
  echo "Unexpected audit root" >&2
  exit 2
}
[[ -d "$repo_root/.git" && -d "$case_root/evaluation" ]] || {
  echo "Repository or completed evaluation is missing" >&2
  exit 2
}
[[ ! -e "$stage" && ! -e "$archive" ]] || {
  echo "Audit staging directory or archive already exists" >&2
  exit 2
}
command -v zip >/dev/null || { echo "zip is not available" >&2; exit 2; }

mkdir -p "$stage/evaluation" "$stage/execution" "$stage/manifests" "$stage/failed_attempts"
cp "$repo_root/benchmark/integrative/provenance/README_auditoria_integracao_real.md" "$stage/README.md"
cp "$case_root/evaluation/"* "$stage/evaluation/"
cp "$case_root/logs/trace.tsv" "$case_root/logs/report.html" "$case_root/logs/timeline.html" \
  "$case_root/logs/dag.html" "$case_root/logs/nextflow.log" "$stage/execution/"
cp "$benchmark_root/logs/integration-driver.log" "$benchmark_root/logs/integration-driver.exit" "$stage/execution/"
cp "$case_root/results/integration/integrative_run_manifest.json" "$stage/manifests/"
cp "$case_root/results/integration/010-input-validation/integrative_inputs/input_validation.json" "$stage/manifests/"
cp "$prepared/h3k27ac_db_evidence/differential_binding_evidence_audit.json" "$stage/manifests/h3k27ac_differential_evidence_audit.json"
cp "$prepared/h3k27me3_db_evidence/differential_binding_evidence_audit.json" "$stage/manifests/h3k27me3_differential_evidence_audit.json"
cp "$prepared/chipseq_multimark_db_evidence/multimark_adapter_audit.json" "$stage/manifests/"
cp "$prepared/rnaseq/rnaseq_run_manifest.json" "$stage/manifests/rnaseq_run_manifest.json"
cp "$prepared/chipseq_multimark_db_evidence/chipseq_run_manifest.json" "$stage/manifests/chipseq_run_manifest.json"

for failed_case in integration_failed_duplicate_basenames integration_failed_peak_namespace; do
  failed_root="$benchmark_root/cases/$failed_case/logs"
  if [[ -d "$failed_root" ]]; then
    mkdir -p "$stage/failed_attempts/$failed_case"
    [[ ! -f "$failed_root/nextflow.log" ]] || cp "$failed_root/nextflow.log" "$stage/failed_attempts/$failed_case/"
    [[ ! -f "$failed_root/trace.tsv" ]] || cp "$failed_root/trace.tsv" "$stage/failed_attempts/$failed_case/"
  fi
done

for log_name in \
  h3k27ac.17218.err h3k27ac.17218.out \
  h3k27me3.17219.err h3k27me3.17219.out \
  integration-evaluation.17235.err integration-evaluation.17235.out; do
  [[ ! -f "$benchmark_root/logs/db-evidence/$log_name" ]] || \
    cp "$benchmark_root/logs/db-evidence/$log_name" "$stage/failed_attempts/"
  [[ ! -f "$benchmark_root/logs/$log_name" ]] || \
    cp "$benchmark_root/logs/$log_name" "$stage/failed_attempts/"
done

(
  cd "$stage"
  find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS
  zip -qr "$archive" .
)
sha256sum "$archive" > "$archive.sha256"
rm -rf -- "$stage"
printf '%s\n' "$archive"
