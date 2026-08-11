#!/usr/bin/env bash

set -euo pipefail

validation_root=${1:?validation root is required}
conda_bin=${2:?conda executable is required}
runtime_env=${3:-rna-tools}
queue=${4:-general}
resume_mode=${5:-false}
repo_root="${validation_root}/repo"

case "$validation_root" in
    /*/helixforge-validation-*) ;;
    *) echo "Refusing unexpected validation root: $validation_root" >&2; exit 2 ;;
esac

test -d "$repo_root/.git"
test -x "$conda_bin"
test -s "$validation_root/nextflow.jar"

case "$resume_mode" in
    true) resume_args=(-resume) ;;
    false) resume_args=() ;;
    *) echo "resume mode must be true or false" >&2; exit 2 ;;
esac

cd "$repo_root"
env NXF_HOME="$validation_root/.nextflow-home" \
    "$conda_bin" run -n "$runtime_env" java \
    -jar "$validation_root/nextflow.jar" \
    -log "$validation_root/trim-stub.nextflow.log" \
    run tests/native_trim_galore/main.nf \
    -c tests/native_trim_galore/nextflow.config \
    "${resume_args[@]}" \
    -stub-run \
    -ansi-log false \
    -process.executor=slurm \
    -process.queue="$queue" \
    -work-dir "$validation_root/work/trim-stub" \
    --read1 tests/fixtures/trim_galore/input_R1.fastq \
    --read2 tests/fixtures/trim_galore/input_R2.fastq \
    --target_dir "$validation_root/results/trim-stub/target" \
    --outdir "$validation_root/results/trim-stub"
