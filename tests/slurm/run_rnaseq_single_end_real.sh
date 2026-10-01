#!/usr/bin/env bash
set -euo pipefail

# Run on a Slurm site with the certified Nextflow launcher and RNA tools.
# Usage: CONDA_BASE=/shared/conda NEXTFLOW_BIN=nextflow \
#   bash tests/slurm/run_rnaseq_single_end_real.sh /shared/validation/single-end partition
case_root=${1:?provide a new, persistent case directory}
queue=${2:?provide a Slurm partition}
conda_base=${CONDA_BASE:?set CONDA_BASE to the site Conda installation}
nextflow_bin=${NEXTFLOW_BIN:-nextflow}
rna_env=${RNA_ENV:-rna-tools}
python_env=${PYTHON_ENV:-python-list}
r_env=${R_ENV:-r-analysis}
repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
runtime_path="${conda_base}/envs/${rna_env}/bin:${conda_base}/envs/${r_env}/bin:${conda_base}/envs/${python_env}/bin:/usr/bin:/bin"

[[ ! -e "$case_root" ]] || { echo "Refusing to overwrite $case_root" >&2; exit 2; }
for command_name in python3 salmon fastqc trim_galore multiqc Rscript; do
    PATH="$runtime_path" command -v "$command_name" >/dev/null || {
        echo "Missing $command_name from the site Conda environments" >&2; exit 2;
    }
done
[[ "$("$nextflow_bin" -version 2>&1)" == *"version 25.10.7"* ]] || {
    echo "Nextflow 25.10.7 is required" >&2; exit 2;
}
"${conda_base}/envs/${python_env}/bin/python3" "$repo_root/tests/slurm/generate_rnaseq_fixture.py" \
    --repo-root "$repo_root" --case-root "$case_root" \
    --conda-base "$conda_base" --layout single
mkdir -p "$case_root/logs" "$case_root/traces" "$case_root/cache"
export NXF_CACHE_DIR="$case_root/cache"

run_pipeline() {
    local label=$1
    shift
    env PATH="$runtime_path" "$nextflow_bin" -log "$case_root/logs/$label.nextflow.log" run "$repo_root/main.nf" \
        -c "$repo_root/tests/slurm/rnaseq-production.config" \
        -ansi-log false -work-dir "$case_root/work" -process.queue="$queue" "$@" \
        --workflow rnaseq --rnaseq_run_mode full \
        --rnaseq_analysis_mode quantification --rnaseq_native_alignment false \
        --rnaseq_config "$case_root/pipeline_config.sh" \
        --rnaseq_de_spec "$case_root/analysis_spec.json" \
        --rnaseq_library_protocol full_length \
        --rnaseq_counts_from_abundance lengthScaledTPM \
        --rnaseq_report_genes "$case_root/candidate_genes.txt" \
        --salmon_index_queue "$queue" --salmon_quant_queue "$queue" \
        --tx2gene_queue "$queue" --tximport_queue "$queue" \
        --deseq2_model_queue "$queue" --deseq2_contrast_queue "$queue" \
        --outdir "$case_root/results"
    cp "$case_root/results/pipeline_info/execution_trace.tsv" "$case_root/traces/$label.tsv"
}

run_pipeline baseline
run_pipeline resume -resume
python3 - "$case_root" <<'PY'
import csv
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
manifest = json.loads((root / "results/rnaseq/rnaseq_run_manifest.json").read_text())
assert len(manifest["samples"]) == 4
assert all(sample.get("library_layout") == "single" for sample in manifest["samples"])
assert all((sample.get("fragment_length_mean"), sample.get("fragment_length_sd")) == (200, 80)
           for sample in manifest["samples"])
with (root / "traces/resume.tsv").open(newline="") as handle:
    rows = list(csv.DictReader(handle, delimiter="\t"))
for process in ("TRIM_GALORE_SINGLE", "MERGE_FASTQ_SINGLE", "SALMON_QUANT",
                "SALMON_IMPORT", "DESEQ2_MODEL", "DESEQ2_CONTRAST"):
    matches = [row for row in rows if process in row["name"]]
    assert matches, f"missing {process} in resume trace"
    assert all(row["status"] == "CACHED" for row in matches), (process, matches)
assert (root / "results/pipeline_info/native_de/aggregate/differential_expression_results.tsv").is_file()
PY
printf '[OK] single-end Slurm execution and cache: %s\n' "$case_root"
