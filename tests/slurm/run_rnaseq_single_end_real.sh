#!/usr/bin/env bash
set -euo pipefail

# Controlled, real-tool Slurm validation. The login node only orchestrates;
# fixture generation, runtime preflight, validation, and scientific processes
# run on compute nodes. Nothing is deleted automatically.
#
# VALIDATION_BASE=/scratch/HELIXFORGE_WORKSPACE/validation \
# CONDA_BASE=/home/USER/miniconda3 NEXTFLOW_BIN=/home/USER/.local/bin/nextflow-25.10.7 \
# bash tests/slurm/run_rnaseq_single_end_real.sh "$VALIDATION_BASE/case-unique" general baseline
#
# Third argument: baseline (four runs), technical (five runs/four samples), or
# resume-only (continue a previously completed baseline in the same case).

case_root=${1:?provide a new, isolated case directory}
queue=${2:?provide the Slurm partition}
requested_case_kind=${3:-baseline}
case_kind=$requested_case_kind
helper_mode=${4:-driver}
validation_base=${VALIDATION_BASE:?set the absolute parent directory for validation cases}
conda_base=${CONDA_BASE:?set the site Conda installation}
nextflow_bin=${NEXTFLOW_BIN:?set the official Nextflow 25.10.7 launcher}
rna_env=${RNA_ENV:-rna-tools}
python_env=${PYTHON_ENV:-python-list}
r_env=${R_ENV:-r-analysis}
max_jobs=${HELIXFORGE_MAX_SLURM_JOBS:-5}
if [[ -n "${SLURM_JOB_ID:-}" ]]; then
    repo_root=${HF_REPO_ROOT:?Slurm helper requires the explicitly exported source root}
else
    repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
fi

[[ "$case_root" == /* && "$validation_base" == /* ]] || {
    echo 'Case and VALIDATION_BASE must be absolute paths' >&2; exit 2;
}
case_root=$(realpath -m "$case_root")
validation_base=$(realpath -m "$validation_base")
[[ -d "$validation_base" && "$validation_base" != / && "$case_root" == "$validation_base/"* ]] || {
    echo 'Case must be beneath the existing, explicitly named VALIDATION_BASE' >&2; exit 2;
}
[[ "$max_jobs" =~ ^[1-8]$ ]] || {
    echo 'HELIXFORGE_MAX_SLURM_JOBS must be an integer from 1 to 8' >&2; exit 2;
}
[[ -d "$conda_base/envs/$rna_env" && -d "$conda_base/envs/$r_env" && -d "$conda_base/envs/$python_env" ]] || {
    echo 'One or more required site Conda environments are absent' >&2; exit 2;
}
runtime_path="$conda_base/envs/$rna_env/bin:$conda_base/envs/$r_env/bin:$conda_base/envs/$python_env/bin:/usr/bin:/bin"
python_bin="$conda_base/envs/$python_env/bin/python3"
certified_python="$conda_base/envs/$rna_env/bin/python3"
[[ -x "$python_bin" && -x "$certified_python" ]] || {
    echo 'Required Python executable is absent' >&2; exit 2;
}
if [[ "$nextflow_bin" != /* ]]; then
    nextflow_bin=$(command -v "$nextflow_bin")
fi
[[ -x "$nextflow_bin" && "$nextflow_bin" != *.jar ]] || {
    echo 'NEXTFLOW_BIN must be an executable official launcher, not a JAR' >&2; exit 2;
}

if [[ "$helper_mode" != driver ]]; then
    [[ -n "${SLURM_JOB_ID:-}" ]] || {
        echo 'Helper work must run in a Slurm compute-node job' >&2; exit 2;
    }
    export PATH="$runtime_path"
    case "$helper_mode" in
        preflight-job)
            for tool in java salmon fastqc trim_galore cutadapt multiqc Rscript python3 gzip sha256sum; do
                command -v "$tool" >/dev/null || { echo "Missing site runtime: $tool" >&2; exit 3; }
            done
            [[ "$(command -v python3)" == "$certified_python" ]] || {
                echo 'The workflow would see a non-certified Python executable' >&2; exit 3;
            }
            python3 -c 'import jsonschema'
            Rscript -e 'stopifnot(requireNamespace("DESeq2", quietly=TRUE), requireNamespace("tximport", quietly=TRUE))'
            salmon --version
            fastqc --version
            trim_galore --version
            multiqc --version
            ;;
        fixture-job)
            fixture_args=()
            [[ "$case_kind" != technical ]] || fixture_args=(--split-one-sample)
            "$python_bin" "$repo_root/tests/slurm/generate_rnaseq_fixture.py" \
                --repo-root "$repo_root" --case-root "$case_root" \
                --conda-base "$conda_base" --layout single "${fixture_args[@]}"
            ;;
        validate-job)
            scenario=${5:?provide baseline or resume validation scenario}
            "$python_bin" "$repo_root/tests/slurm/validate_rnaseq_real.py" \
                "$case_root" --output "$case_root/validation-scientific-$scenario.json"
            split_args=()
            [[ "$case_kind" != technical ]] || split_args=(--technical-split)
            "$python_bin" "$repo_root/tests/slurm/validate_rnaseq_single_end.py" \
                "$case_root" --scenario "$scenario" "${split_args[@]}"
            ;;
        *) echo "Unknown helper mode: $helper_mode" >&2; exit 2 ;;
    esac
    exit 0
fi

[[ -z "${SLURM_JOB_ID:-}" ]] || {
    echo 'Nextflow must be launched from the management node, not inside sbatch' >&2; exit 2;
}
[[ "$case_kind" == baseline || "$case_kind" == technical || "$case_kind" == resume-only ]] || {
    echo 'Case kind must be baseline, technical, or resume-only' >&2; exit 2;
}
runtime_version=$(PATH="$runtime_path" "$nextflow_bin" -version 2>&1)
[[ "$runtime_version" == *'version 25.10.7'* ]] || {
    printf 'Expected official Nextflow 25.10.7 launcher, observed:\n%s\n' "$runtime_version" >&2
    exit 4
}

if [[ "$case_kind" == resume-only ]]; then
    [[ -s "$case_root/case_kind.txt" && -s "$case_root/traces/baseline.tsv" ]] || {
        echo 'Cannot resume a case without its baseline trace and kind' >&2; exit 2;
    }
    case_kind=$(<"$case_root/case_kind.txt")
    [[ "$case_kind" == baseline || "$case_kind" == technical ]] || exit 2
else
    [[ ! -e "$case_root" ]] || {
        echo "Refusing to overwrite existing case: $case_root" >&2; exit 2;
    }
    mkdir -p "$case_root/logs" "$case_root/traces" "$case_root/cache" "$case_root/audit"
    printf '%s\n' "$case_kind" > "$case_root/case_kind.txt"
fi
mkdir -p "$case_root/cache" "$case_root/audit"
case_id=$(printf '%s' "$case_root" | sha256sum | cut -c1-12)
run_name="hf_se_$case_id"
printf '%s\n' "$run_name" > "$case_root/audit/run_name.txt"
export NXF_CACHE_DIR="$case_root/cache" NXF_VER=25.10.7 HELIXFORGE_MAX_SLURM_JOBS="$max_jobs"

submit_helper() {
    local label=$1
    local mode=$2
    local scenario=${3:-}
    local -a args=(
        --wait --parsable --partition="$queue" --job-name="$label"
        --cpus-per-task=1 --mem=2G --time=00:20:00
        --export="ALL,HF_REPO_ROOT=$repo_root"
        --chdir="$repo_root" --output="$case_root/logs/${label}-%j.out"
        "$repo_root/tests/slurm/run_rnaseq_single_end_real.sh"
        "$case_root" "$queue" "$case_kind" "$mode"
    )
    [[ -z "$scenario" ]] || args+=("$scenario")
    local job_id
    job_id=$(sbatch "${args[@]}")
    printf '%s\t%s\n' "$label" "$job_id" >> "$case_root/audit/helper_jobs.tsv"
}

run_pipeline() {
    local scenario=$1
    local -a session_args=(-name "$run_name")
    if [[ "$scenario" == resume ]]; then
        session_args=(-resume "$run_name")
    fi
    cd "$repo_root"
    env PATH="$runtime_path" \
        "$nextflow_bin" -log "$case_root/logs/$scenario.nextflow.log" \
        run main.nf -c tests/slurm/rnaseq-single-end.config \
        -ansi-log false "${session_args[@]}" -work-dir "$case_root/work" \
        -process.queue="$queue" \
        --workflow rnaseq --rnaseq_run_mode full \
        --rnaseq_analysis_mode quantification --rnaseq_native_alignment false \
        --rnaseq_config "$case_root/pipeline_config.sh" \
        --rnaseq_de_spec "$case_root/analysis_spec.json" \
        --rnaseq_library_protocol full_length \
        --rnaseq_counts_from_abundance lengthScaledTPM \
        --rnaseq_report_enabled true \
        --rnaseq_report_genes "$case_root/candidate_genes.txt" \
        --rnaseq_report_outdir "$case_root/pipeline/090-search-gene" \
        --rnaseq_report_title 'Synthetic single-end RNA-seq validation' \
        --rnaseq_report_expression_unit TPM \
        --rnaseq_report_life_stage_levels 'adult,unknown' \
        --salmon_index_queue "$queue" --salmon_quant_queue "$queue" \
        --tx2gene_queue "$queue" --tximport_queue "$queue" \
        --deseq2_model_queue "$queue" --deseq2_contrast_queue "$queue" \
        --outdir "$case_root/results"
    cp "$case_root/results/pipeline_info/execution_trace.tsv" "$case_root/traces/$scenario.tsv"
}

resume_guard() {
    local action=$1
    cd "$repo_root"
    PATH="$runtime_path" "$certified_python" "$repo_root/bin/helixforge-resume-guard" \
        "$action" --run-name "$run_name" \
        --receipt "$case_root/audit/resume-receipt.json" \
        --work-dir "$case_root/work" --launch-dir "$repo_root" \
        --cache-dir "$case_root/cache" --nextflow "$nextflow_bin"
}

if [[ "$requested_case_kind" != resume-only ]]; then
    submit_helper hf-se-preflight preflight-job
    submit_helper hf-se-fixture fixture-job
    run_pipeline baseline
    submit_helper hf-se-validate validate-job baseline
    resume_guard capture
elif [[ ! -s "$case_root/audit/resume-receipt.json" ]]; then
    resume_guard capture
fi
resume_guard check
run_pipeline resume
submit_helper hf-se-resume-check validate-job resume
printf '[OK] Single-end Slurm baseline and resume: %s\n' "$case_root"
