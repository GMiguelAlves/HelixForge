#!/usr/bin/env bash
set -euo pipefail

repo_root=${1:?repository root is required}
python_bin=${2:?Python executable is required}
rscript_bin=${3:?Rscript executable is required}
output=${4:?output report is required}
test -n "${SLURM_JOB_ID:-}"

scripts="$repo_root/benchmark/rnaseq/scripts"
configs="$repo_root/benchmark/rnaseq/configs"

for script in \
    prepare_synthetic_reference.py fasta_to_fastq.py \
    validate_synthetic_dataset.py build_helixforge_inputs.py; do
    "$python_bin" -m py_compile "$scripts/$script"
done

"$python_bin" -c 'import json, pathlib, sys; [json.loads(path.read_text()) for path in map(pathlib.Path, sys.argv[1:])]' \
    "$configs/synthetic_design.json" "$configs/synthetic_de_spec.json"
"$rscript_bin" -e 'parse(file=commandArgs(TRUE)[1])' "$scripts/build_synthetic_truth.R"
bash -n "$scripts/slurm_runtime_preflight.sh"
bash -n "$scripts/test_benchmark_scripts.sh"

printf '{"status":"pass","slurm_job_id":"%s","node":"%s"}\n' \
    "$SLURM_JOB_ID" "$(hostname)" > "$output"
