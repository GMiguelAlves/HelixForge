#!/usr/bin/env bash
set -euo pipefail

repo_root=${1:?repository root is required}
python_bin=${2:?Python executable is required}
rscript_bin=${3:?Rscript executable is required}
output=${4:?output report is required}
test -n "${SLURM_JOB_ID:-}"

scripts="$repo_root/benchmark/rnaseq/scripts"
common="$scripts/common"
synthetic="$scripts/synthetic"
gse52778="$scripts/gse52778"
tests="$scripts/tests"
configs="$repo_root/benchmark/rnaseq/configs"

for script in \
    common/compare_independent.py common/compare_gse52778_independent.py \
    common/compare_reference_repeats.py common/compare_helixforge_repeats.py \
    common/prepare_gencode_reference.py \
    synthetic/prepare_synthetic_reference.py synthetic/fasta_to_fastq.py \
    synthetic/validate_synthetic_dataset.py synthetic/build_helixforge_inputs.py \
    synthetic/evaluate_synthetic.py synthetic/validate_helixforge_run.py \
    synthetic/summarize_performance.py synthetic/verify_audit_archive.py \
    synthetic/prepare_stage9b1_figures.py synthetic/finalize_stage9b1_figures.py \
    gse52778/validate_gse52778_metadata.py gse52778/validate_gse52778_fastq.py \
    gse52778/finalize_gse52778_download.py gse52778/build_gse52778_inputs.py \
    gse52778/validate_gse52778_run.py gse52778/summarize_gse52778_comparison.py \
    gse52778/evaluate_gse52778_biology.py gse52778/measure_gse52778_concordance.py \
    gse52778/summarize_gse52778_qc.py gse52778/summarize_gse52778_performance.py; do
    "$python_bin" -m py_compile "$scripts/$script"
done

"$python_bin" -c \
    'import sys; sys.path.insert(0, sys.argv[1]); import summarize_performance as s; assert s.parse_duration("327ms") == 0.327; assert s.parse_duration("1m 4.2s") == 64.2; rows=[{"submit":"2026-01-01 00:00:00.000","duration":"5s","realtime":"4s"},{"submit":"2026-01-01 00:00:01.000","duration":"5s","realtime":"4s"}]; assert s.peak_running_concurrency(rows) == 2' \
    "$synthetic"

"$python_bin" -c 'import json, pathlib, sys; [json.loads(path.read_text()) for path in map(pathlib.Path, sys.argv[1:])]' \
    "$configs/synthetic_design.json" "$configs/synthetic_de_spec.json"
"$rscript_bin" -e 'invisible(parse(file=commandArgs(TRUE)[1]))' "$synthetic/build_synthetic_truth.R"
"$rscript_bin" -e 'invisible(parse(file=commandArgs(TRUE)[1]))' "$synthetic/independent_tximport_deseq2.R"
"$rscript_bin" -e 'invisible(parse(file=commandArgs(TRUE)[1]))' "$gse52778/independent_gse52778_tximport_deseq2.R"
"$rscript_bin" -e 'invisible(parse(file=commandArgs(TRUE)[1]))' "$synthetic/plot_stage9b1_figures.R"
"$rscript_bin" -e 'invisible(parse(file=commandArgs(TRUE)[1]))' "$gse52778/plot_gse52778_benchmark.R"
bash -n "$common/slurm_runtime_preflight.sh"
bash -n "$common/slurm_create_environment.sh"
bash -n "$common/slurm_download_reference.sh"
bash -n "$common/slurm_restore_temurin21.sh"
bash -n "$synthetic/run_independent_reference.sh"
bash -n "$synthetic/slurm_generate_polyester.sh"
bash -n "$synthetic/slurm_convert_polyester_sample.sh"
bash -n "$synthetic/run_helixforge_synthetic.sh"
bash -n "$synthetic/run_stage9b1_figures.sh"
bash -n "$gse52778/slurm_prepare_gse52778_metadata.sh"
bash -n "$gse52778/download_gse52778.sh"
bash -n "$gse52778/slurm_prepare_gencode_reference.sh"
bash -n "$gse52778/run_helixforge_gse52778.sh"
bash -n "$gse52778/slurm_finalize_gse52778.sh"
bash -n "$tests/test_benchmark_scripts.sh"

printf '{"status":"pass","slurm_job_id":"%s","node":"%s"}\n' \
    "$SLURM_JOB_ID" "$(hostname)" > "$output"
