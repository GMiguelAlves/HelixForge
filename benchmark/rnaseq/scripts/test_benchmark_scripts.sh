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
    validate_synthetic_dataset.py build_helixforge_inputs.py evaluate_synthetic.py \
    compare_independent.py compare_reference_repeats.py compare_helixforge_repeats.py \
    validate_helixforge_run.py summarize_performance.py; do
    "$python_bin" -m py_compile "$scripts/$script"
done

"$python_bin" -c \
    'import sys; sys.path.insert(0, sys.argv[1]); import summarize_performance as s; assert s.parse_duration("327ms") == 0.327; assert s.parse_duration("1m 4.2s") == 64.2; rows=[{"submit":"2026-01-01 00:00:00.000","duration":"5s","realtime":"4s"},{"submit":"2026-01-01 00:00:01.000","duration":"5s","realtime":"4s"}]; assert s.peak_running_concurrency(rows) == 2' \
    "$scripts"

"$python_bin" -c 'import json, pathlib, sys; [json.loads(path.read_text()) for path in map(pathlib.Path, sys.argv[1:])]' \
    "$configs/synthetic_design.json" "$configs/synthetic_de_spec.json"
"$rscript_bin" -e 'invisible(parse(file=commandArgs(TRUE)[1]))' "$scripts/build_synthetic_truth.R"
"$rscript_bin" -e 'invisible(parse(file=commandArgs(TRUE)[1]))' "$scripts/independent_tximport_deseq2.R"
bash -n "$scripts/slurm_runtime_preflight.sh"
bash -n "$scripts/test_benchmark_scripts.sh"
bash -n "$scripts/slurm_create_environment.sh"
bash -n "$scripts/slurm_download_reference.sh"
bash -n "$scripts/run_independent_reference.sh"
bash -n "$scripts/slurm_generate_polyester.sh"
bash -n "$scripts/slurm_convert_polyester_sample.sh"
bash -n "$scripts/run_helixforge_synthetic.sh"
bash -n "$scripts/archive_stage9b1.sh"

printf '{"status":"pass","slurm_job_id":"%s","node":"%s"}\n' \
    "$SLURM_JOB_ID" "$(hostname)" > "$output"
