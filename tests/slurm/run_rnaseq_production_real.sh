#!/usr/bin/env bash

set -euo pipefail

validation_root=${1:?validation root is required}
conda_bin=${2:?conda executable is required}
rna_env=${3:-rna-tools}
python_env=${4:-python-list}
r_env=${5:-r-analysis}
queue=${6:-general}
mode=${7:-driver}
case_name=${8:-rnaseq-production-real}
repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
case_root="${validation_root}/results/${case_name}"
conda_root=$(cd "$(dirname "$conda_bin")/.." && pwd)
runtime_path="${conda_root}/envs/${r_env}/bin:${conda_root}/envs/${rna_env}/bin:${conda_root}/envs/${python_env}/bin:/usr/bin:/bin"
nextflow_jar="${validation_root}/nextflow.jar"
work_root="${validation_root}/work/${case_name}"

case "$validation_root" in
    /scratch/Schisto-epigenetics/gustavo/helixforge-validation-*) ;;
    *) echo "Refusing unexpected validation root: $validation_root" >&2; exit 2 ;;
esac

test -d "$repo_root/.git"
test -x "$conda_bin"
test -s "$nextflow_jar"

if [[ "$mode" == "preflight-job" ]]; then
    test -n "${SLURM_JOB_ID:-}"
    export PATH="$runtime_path"
    missing=0
    for command_name in java salmon fastqc trim_galore cutadapt multiqc Rscript python3; do
        if command_path=$(command -v "$command_name"); then
            printf '[OK] %s=%s\n' "$command_name" "$command_path"
        else
            printf '[MISSING] %s\n' "$command_name" >&2
            missing=1
        fi
    done
    [[ "$missing" -eq 0 ]] || exit 3
    salmon --version
    fastqc --version
    trim_galore --version
    multiqc --version
    Rscript -e 'stopifnot(requireNamespace("DESeq2", quietly=TRUE), requireNamespace("tximport", quietly=TRUE)); cat(as.character(packageVersion("DESeq2")), "\n")'
    exit 0
fi

if [[ "$mode" == "fixture-job" ]]; then
    test -n "${SLURM_JOB_ID:-}"
    variant=${9:?fixture variant is required}
    "${conda_root}/envs/${python_env}/bin/python3" \
        "$repo_root/tests/slurm/generate_rnaseq_fixture.py" \
        --repo-root "$repo_root" \
        --case-root "$case_root" \
        --conda-base "$conda_root" \
        --variant "$variant"
    exit 0
fi

if [[ "$mode" == "validate-job" ]]; then
    test -n "${SLURM_JOB_ID:-}"
    scenario=${9:?validation scenario is required}
    "${conda_root}/envs/${python_env}/bin/python3" \
        "$repo_root/tests/slurm/validate_rnaseq_real.py" \
        "$case_root" --output "$case_root/validation-${scenario}.json"
    exit 0
fi

if [[ "$mode" != "driver" ]]; then
    echo "mode must be driver, preflight-job, fixture-job, or validate-job" >&2
    exit 2
fi
if [[ -e "$case_root" ]]; then
    echo "Refusing to overwrite an existing validation case: $case_root" >&2
    exit 2
fi

mkdir -p "$case_root/logs" "$case_root/traces"

submit_helper() {
    local job_name=$1
    local helper_mode=$2
    local extra=${3:-}
    local job_id
    local -a args=(
        --wait --parsable
        --job-name="$job_name"
        --partition="$queue"
        --cpus-per-task=1
        --mem=2G
        --time=00:10:00
        --output="$case_root/logs/${job_name}-%j.out"
        "$0" "$validation_root" "$conda_bin" "$rna_env" "$python_env" "$r_env" "$queue" "$helper_mode" "$case_name"
    )
    [[ -z "$extra" ]] || args+=("$extra")
    job_id=$(sbatch "${args[@]}")
    printf '%s\t%s\n' "$job_name" "$job_id" >> "$case_root/helper_jobs.tsv"
}

run_pipeline() {
    local scenario=$1
    local resume=$2
    local validate_mappings=$3
    local -a resume_args=()
    [[ "$resume" == true ]] && resume_args=(-resume)
    cd "$repo_root"
    env PATH="$runtime_path" \
        NXF_HOME="${repo_root}/.nextflow-home" \
        "${conda_root}/envs/${rna_env}/bin/java" \
        -jar "$nextflow_jar" \
        -log "$case_root/logs/${scenario}.nextflow.log" \
        run main.nf \
        -c tests/slurm/rnaseq-production.config \
        -ansi-log false \
        "${resume_args[@]}" \
        -work-dir "$work_root" \
        -process.queue="$queue" \
        --workflow rnaseq \
        --outdir "$case_root/results" \
        --rnaseq_config "$case_root/pipeline_config.sh" \
        --legacy_dry_run true \
        --rnaseq_analysis_mode quantification \
        --rnaseq_run_mode full \
        --rnaseq_native_alignment false \
        --rnaseq_de_spec "$case_root/analysis_spec.json" \
        --rnaseq_library_protocol full_length \
        --rnaseq_counts_from_abundance lengthScaledTPM \
        --salmon_validate_mappings "$validate_mappings" \
        --salmon_index_queue "$queue" \
        --salmon_quant_queue "$queue" \
        --tx2gene_queue "$queue" \
        --tximport_queue "$queue" \
        --deseq2_model_queue "$queue" \
        --deseq2_contrast_queue "$queue"
    cp "$case_root/results/pipeline_info/execution_trace.tsv" "$case_root/traces/${scenario}.tsv"
}

submit_helper hf-rna-preflight preflight-job
submit_helper hf-rna-fixture fixture-job baseline

run_pipeline baseline false true
submit_helper hf-rna-validate validate-job baseline

run_pipeline identical true true
"${conda_root}/envs/${python_env}/bin/python3" \
    "$repo_root/tests/slurm/assert_rnaseq_cache.py" \
    "$case_root/traces/identical.tsv" identical

submit_helper hf-rna-fastq fixture-job fastq
run_pipeline fastq-change true true
"${conda_root}/envs/${python_env}/bin/python3" \
    "$repo_root/tests/slurm/assert_rnaseq_cache.py" \
    "$case_root/traces/fastq-change.tsv" fastq
submit_helper hf-rna-validate-fastq validate-job fastq

submit_helper hf-rna-transcriptome fixture-job transcriptome
run_pipeline transcriptome-change true true
"${conda_root}/envs/${python_env}/bin/python3" \
    "$repo_root/tests/slurm/assert_rnaseq_cache.py" \
    "$case_root/traces/transcriptome-change.tsv" transcriptome
submit_helper hf-rna-validate-transcriptome validate-job transcriptome

run_pipeline parameter-change true false
"${conda_root}/envs/${python_env}/bin/python3" \
    "$repo_root/tests/slurm/assert_rnaseq_cache.py" \
    "$case_root/traces/parameter-change.tsv" parameters
submit_helper hf-rna-validate-parameters validate-job parameters

echo "[OK] Production RNA-seq and cache matrix passed."
echo "[OK] Case root: $case_root"
