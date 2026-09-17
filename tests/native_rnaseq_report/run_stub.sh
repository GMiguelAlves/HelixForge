#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/../.." && pwd)"
nextflow_bin="${NEXTFLOW:-nextflow}"
"${nextflow_bin}" run "${script_dir}/main.nf" -c "${script_dir}/nextflow.config" -stub-run
test -s "${script_dir}/results/rnaseq/090-search-gene/results/gene_set_report.html"
test -s "${script_dir}/results/rnaseq/090-search-gene/results/manifest.json"

fixture="${repo_root}/tests/fixtures/native_rnaseq_report"
reentry_root="$(mktemp -d)"
trap 'rm -rf -- "$reentry_root"' EXIT
"${nextflow_bin}" run "${repo_root}" -c "${script_dir}/nextflow.config" \
    -stub-run -ansi-log false -work-dir "${reentry_root}/work" \
    --workflow rnaseq \
    --rnaseq_run_mode report_reentry \
    --rnaseq_report_import_manifest "${fixture}/import_manifest.json" \
    --rnaseq_report_abundance "${fixture}/tpm_matrix.tsv" \
    --rnaseq_report_samples "${fixture}/quant_samples.tsv" \
    --rnaseq_report_annotation "${fixture}/annotation.gtf" \
    --rnaseq_report_de_results "${fixture}/DEGs_all_results.tsv" \
    --rnaseq_report_de_manifest "${fixture}/de_manifest.json" \
    --rnaseq_report_genes "${fixture}/genes.txt" \
    --rnaseq_report_outdir "${reentry_root}/results/rnaseq/090-search-gene" \
    --outdir "${reentry_root}/results"
test -s "${reentry_root}/results/rnaseq/090-search-gene/results/gene_set_report.html"
test -s "${reentry_root}/results/rnaseq/090-search-gene/results/manifest.json"
trace="${reentry_root}/results/pipeline_info/execution_trace.tsv"
test -s "$trace"
grep -q 'RNASEQ_REPORT_CONTEXT' "$trace"
grep -q 'RNASEQ_GENE_REPORT' "$trace"
if grep -Eq 'FASTQC|TRIM_GALORE|SALMON|TXIMPORT|DESEQ2' "$trace"; then
    echo 'report_reentry scheduled an upstream scientific process' >&2
    exit 1
fi
