#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
nextflow run "${script_dir}/main.nf" -c "${script_dir}/nextflow.config" -stub-run
test -s "${script_dir}/results/rnaseq/090-search-gene/results/gene_set_report.html"
test -s "${script_dir}/results/rnaseq/090-search-gene/results/manifest.json"
