#!/usr/bin/env bash

set -euo pipefail

project_root="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

required=(
    "pipelines/rnaseq/legacy/rnaseq_pipeline.sh"
    "pipelines/rnaseq/legacy/config/pipeline_config.sh"
    "pipelines/rnaseq/legacy/scripts/030-qc-fastq/run_qc_project.sh"
    "pipelines/rnaseq/legacy/scripts/040-alignment/run_alignment_project.sh"
    "pipelines/rnaseq/legacy/scripts/040-alignment/run_star_quant_project.sh"
    "pipelines/rnaseq/legacy/scripts/050-quantification/quantification_job.sh"
    "pipelines/rnaseq/legacy/scripts/060-deg-analysis/run_deg_analysis_slurm.sh"
    "pipelines/chipseq/legacy/chipseq_pipeline.sh"
    "pipelines/chipseq/legacy/config/pipeline_config.sh"
    "pipelines/chipseq/legacy/scripts/010-reference/prepare_reference.sh"
    "pipelines/chipseq/legacy/scripts/080-peak-calling/call_peaks.sh"
    "pipelines/chipseq/legacy/scripts/120-differential-binding/differential_binding.sh"
    "pipelines/integrative/legacy/integrative_pipeline.sh"
    "pipelines/integrative/legacy/config/pipeline_config.sh"
    "pipelines/integrative/legacy/scripts/integrative_core.py"
    "pipelines/integrative/legacy/scripts/r/visualize_integrative.R"
)

missing=0
for relative in "${required[@]}"; do
    if [[ ! -f "${project_root}/${relative}" ]]; then
        echo "MISSING ${relative}" >&2
        missing=1
    fi
done

[[ "$missing" -eq 0 ]] || exit 1
printf 'Validated %d legacy entry points.\n' "${#required[@]}"

