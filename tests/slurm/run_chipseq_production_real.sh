#!/usr/bin/env bash

set -euo pipefail

validation_root=${1:?validation root is required}
conda_bin=${2:?conda executable is required}
rna_env=${3:-rna-tools}
chip_env=${4:-chipseq}
r_env=${5:-r-analysis}
python_env=${6:-python-list}
queue=${7:-general}
mode=${8:-driver}
case_name=${9:-chipseq-production-real}
consensus_method=${HELIXFORGE_CHIPSEQ_CONSENSUS_METHOD:-union}

if [[ -n "${SLURM_JOB_ID:-}" ]]; then
    repo_root=${HELIXFORGE_REPO_ROOT:?HELIXFORGE_REPO_ROOT is required in Slurm helpers}
else
    repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
fi
case_root="${validation_root}/results/${case_name}"
result_root="${case_root}/results"
work_root="${validation_root}/work/${case_name}"
cache_root="${validation_root}/cache/${case_name}"
compat_bin="${validation_root}/runtime/bowtie2-direct"
conda_root=$(cd "$(dirname "$conda_bin")/.." && pwd)
runtime_path="${compat_bin}:${conda_root}/envs/${r_env}/bin:${conda_root}/envs/${chip_env}/bin:${conda_root}/envs/${rna_env}/bin:${conda_root}/envs/${python_env}/bin:/usr/bin:/bin"
if [[ "$consensus_method" == "idr" ]]; then
    idr_env=${HELIXFORGE_IDR_ENV:-idr}
    idr_prefix=${HELIXFORGE_IDR_PREFIX:-${conda_root}/envs/${idr_env}}
    test -x "${idr_prefix}/bin/idr"
elif [[ "$consensus_method" != "union" ]]; then
    echo "Production validation supports consensus method union or idr, observed: $consensus_method" >&2
    exit 2
fi
nextflow_jar=${HELIXFORGE_NEXTFLOW_JAR:-/home/ra236875@bio.ib.unicamp.br/helixforge-validation-20260811/.validation-runtimes/nxf-home-25.10.7/framework/25.10.7/nextflow-25.10.7-one.jar}

case "$validation_root" in
    /scratch/Schisto-epigenetics/gustavo/helixforge-chipseq-validation-*) ;;
    *) echo "Refusing unexpected validation root: $validation_root" >&2; exit 2 ;;
esac
test -e "$repo_root/.git"
test -x "$conda_bin"
test -s "$nextflow_jar"
if [[ -z "${SLURM_JOB_ID:-}" ]]; then
    mkdir -p "$compat_bin"
    ln -sfn "${conda_root}/envs/${chip_env}/bin/bowtie2-align-s" "$compat_bin/bowtie2"
    ln -sfn "${conda_root}/envs/${chip_env}/bin/bowtie2-build-s" "$compat_bin/bowtie2-build"
    ln -sfn "${conda_root}/envs/${chip_env}/bin/python3" "$compat_bin/python3"
    ln -sfn "${conda_root}/envs/${chip_env}/bin/python" "$compat_bin/python"
    if [[ "$consensus_method" == "idr" ]]; then
        ln -sfn "${idr_prefix}/bin/idr" "$compat_bin/idr"
    fi
fi
test -x "$compat_bin/bowtie2"
test -x "$compat_bin/bowtie2-build"
test -x "$compat_bin/python3"
if [[ "$consensus_method" == "idr" ]]; then
    test -x "$compat_bin/idr"
fi

if [[ "$mode" == "preflight-job" ]]; then
    test -n "${SLURM_JOB_ID:-}"
    export PATH="$runtime_path"
    printf 'node=%s\nslurm_job=%s\n' "$(hostname)" "$SLURM_JOB_ID"
    bowtie2 --version | head -n 1
    bowtie2-build --version | head -n 1
    samtools --version | head -n 1
    bedtools --version
    macs3 --version
    featureCounts -v
    bamCoverage --version
    fastqc --version
    multiqc --version
    printf 'Rscript=%s\n' "$(command -v Rscript)"
    Rscript -e 'stopifnot(requireNamespace("DESeq2", quietly=TRUE), requireNamespace("jsonlite", quietly=TRUE)); cat("DESeq2 ", as.character(packageVersion("DESeq2")), "\njsonlite ", as.character(packageVersion("jsonlite")), "\n", sep="")'
    printf 'python3=%s\n' "$(command -v python3)"
    python3 -c 'import pyBigWig; print("pyBigWig", pyBigWig.__version__)'
    if [[ "$consensus_method" == "idr" ]]; then
        idr --version
    fi
    ps --version | head -n 1
    exit 0
fi

if [[ "$mode" == "fixture-job" ]]; then
    test -n "${SLURM_JOB_ID:-}"
    env PATH="$runtime_path" python3 "$repo_root/tests/slurm/generate_chipseq_production_fixture.py" \
        --case-root "$case_root"
    exit 0
fi

if [[ "$mode" == "prepare-job" ]]; then
    test -n "${SLURM_JOB_ID:-}"
    stage=${10:?downstream stage is required}
    env PATH="$runtime_path" python3 "$repo_root/tests/slurm/prepare_chipseq_downstream.py" \
        "$stage" --case-root "$case_root"
    exit 0
fi

if [[ "$mode" == "validate-job" ]]; then
    test -n "${SLURM_JOB_ID:-}"
    env PATH="$runtime_path" python3 "$repo_root/tests/slurm/validate_chipseq_production.py" \
        --case-root "$case_root" --output "$case_root/validation.json" \
        --consensus-method "$consensus_method"
    exit 0
fi

if [[ "$mode" != "driver" && "$mode" != "recovery-driver" ]]; then
    echo "mode must be driver, recovery-driver, preflight-job, fixture-job, prepare-job, or validate-job" >&2
    exit 2
fi

if [[ "$mode" == "driver" ]]; then
    if [[ -e "$case_root" ]]; then
        echo "Refusing to overwrite an existing validation case: $case_root" >&2
        exit 2
    fi
    mkdir -p "$case_root/logs" "$case_root/traces" "$case_root/operational" "$cache_root"
else
    test -d "$case_root/logs"
fi

submit_helper() {
    local job_name=$1 helper_mode=$2 extra=${3:-}
    local -a command=(
        sbatch --wait --parsable
        --job-name="$job_name" --partition="$queue"
        --cpus-per-task=1 --mem=2G --time=00:10:00
        --chdir="$repo_root"
        --export="ALL,HELIXFORGE_REPO_ROOT=$repo_root,HELIXFORGE_NEXTFLOW_JAR=$nextflow_jar"
        --output="$case_root/logs/${job_name}-%j.out"
        "$repo_root/tests/slurm/run_chipseq_production_real.sh"
        "$validation_root" "$conda_bin" "$rna_env" "$chip_env" "$r_env" "$python_env" "$queue"
        "$helper_mode" "$case_name"
    )
    [[ -z "$extra" ]] || command+=("$extra")
    local job_id
    job_id=$("${command[@]}")
    printf '%s\t%s\n' "$job_name" "$job_id" >> "$case_root/helper_jobs.tsv"
}

archive_operational() {
    local stage=$1
    cp "$result_root/pipeline_info/execution_trace.tsv" "$case_root/traces/${stage}.tsv"
    cp "$result_root/pipeline_info/execution_timeline.html" "$case_root/operational/${stage}.timeline.html"
    cp "$result_root/pipeline_info/execution_report.html" "$case_root/operational/${stage}.report.html"
    cp "$result_root/pipeline_info/pipeline_dag.html" "$case_root/operational/${stage}.dag.html"
}

run_stage() {
    local stage=$1
    shift
    cd "$repo_root"
    env PATH="$runtime_path" \
        NXF_HOME="${validation_root}/nxf-home" \
        NXF_CACHE_DIR="$cache_root" \
        "${conda_root}/envs/${rna_env}/bin/java" -Xms128m -Xmx1g -jar "$nextflow_jar" \
        -log "$case_root/logs/${stage}.nextflow.log" \
        run main.nf \
        -c tests/slurm/chipseq-production.config \
        -ansi-log false \
        -work-dir "$work_root/$stage" \
        -process.queue="$queue" \
        --workflow chipseq \
        --outdir "$result_root" \
        --chipseq_config "$case_root/pipeline_config.sh" \
        --legacy_dry_run true \
        "$@"
    archive_operational "$stage"
}

runtime_version=$("${conda_root}/envs/${rna_env}/bin/java" -jar "$nextflow_jar" -version 2>&1)
[[ "$runtime_version" == *"version 25.10.7"* ]] || {
    printf 'Expected certified Nextflow 25.10.7, observed:\n%s\n' "$runtime_version" >&2
    exit 4
}

if [[ "$mode" == "driver" ]]; then
    submit_helper hf-chip-preflight preflight-job
    submit_helper hf-chip-fixture fixture-job
fi

if [[ ! -s "$case_root/traces/full.tsv" ]]; then
    run_stage full \
        --chipseq_run_mode full \
        --chipseq_native_foundation true \
        --chipseq_native_bam_processing true \
        --chipseq_native_peak_calling true \
        --chipseq_native_peak_qc true \
        --chipseq_native_consensus true \
        --chipseq_native_differential_binding true \
        --chipseq_native_peak_annotation true \
        --chipseq_native_tracks true \
        --chipseq_native_report true \
        --chipseq_min_mapq 0 \
        --chipseq_duplicate_mode none \
        --chipseq_peak_caller macs3 \
        --chipseq_peak_type narrow \
        --chipseq_effective_genome_size 9000 \
        --chipseq_peak_q_value 0.5 \
        --chipseq_peak_format BAMPE \
        --chipseq_peak_duplicate_policy all \
        --chipseq_peak_output_dir "$result_root/080-peak-calling" \
        --chipseq_consensus_method "$consensus_method" \
        --chipseq_idr_threshold 0.05 \
        --chipseq_idr_rank_metric signal_value \
        --chipseq_min_replicates 2 \
        --chipseq_db_spec "$case_root/db_spec.json" \
        --chipseq_db_target_dir "$result_root/120-differential-binding" \
        --chipseq_track_bin_size 25 \
        --chipseq_track_normalization CPM \
        --chipseq_track_aggregate true \
        --chipseq_report_title "HelixForge reduced ChIP-seq validation" \
        --bowtie2_index_queue "$queue" --bowtie2_align_queue "$queue" \
        --bam_select_queue "$queue" --bam_duplicates_queue "$queue" \
        --bam_blacklist_queue "$queue" --bam_index_qc_queue "$queue" \
        --macs3_queue "$queue" --peak_qc_queue "$queue" --consensus_queue "$queue" --idr_queue "$queue" \
        --db_count_queue "$queue" --db_model_queue "$queue" --db_contrast_queue "$queue"
fi

submit_helper hf-chip-validate validate-job
printf '[OK] Native full ChIP-seq Slurm validation passed.\n[OK] Case root: %s\n' "$case_root"
