#!/usr/bin/env bash
set -euo pipefail

repo_root=${HELIXFORGE_REPO_ROOT:?HELIXFORGE_REPO_ROOT is required}
scratch_root=${HELIXFORGE_BENCHMARK_ROOT:?HELIXFORGE_BENCHMARK_ROOT is required}
queue=${HELIXFORGE_SLURM_QUEUE:-general}
conda_root=${HELIXFORGE_CONDA_ROOT:-/home/ra236875@bio.ib.unicamp.br/miniconda3}
java_bin=${HELIXFORGE_JAVA:-${conda_root}/envs/rna-tools/bin/java}
nextflow_jar=${HELIXFORGE_NEXTFLOW_JAR:-/home/ra236875@bio.ib.unicamp.br/helixforge-validation-20260811/.validation-runtimes/nxf-home-25.10.7/framework/25.10.7/nextflow-25.10.7-one.jar}
mode=${1:-driver}

case "$scratch_root" in
    /scratch/Schisto-epigenetics/gustavo/helixforge-integrative-synthetic-*) ;;
    *) echo "Refusing unexpected benchmark root: $scratch_root" >&2; exit 2 ;;
esac

truth="$repo_root/benchmark/integrative/datasets/synthetic_truth.tsv"
truth_manifest="$repo_root/benchmark/integrative/datasets/synthetic_truth_manifest.json"
fixture="$scratch_root/fixture"
results="$scratch_root/results"
metrics="$scratch_root/metrics"
logs="$scratch_root/logs"
work="$scratch_root/work"
nxf_home="$scratch_root/nxf-home"

submit_helper() {
    local name=$1 helper=$2
    sbatch --wait --parsable --job-name="$name" --partition="$queue" --cpus-per-task=1 --mem=2G --time=00:20:00 \
        --chdir="$repo_root" --export="ALL,HELIXFORGE_REPO_ROOT=$repo_root,HELIXFORGE_BENCHMARK_ROOT=$scratch_root,HELIXFORGE_SLURM_QUEUE=$queue,HELIXFORGE_CONDA_ROOT=$conda_root,HELIXFORGE_JAVA=$java_bin,HELIXFORGE_NEXTFLOW_JAR=$nextflow_jar" \
        --output="$logs/${name}-%j.out" "$repo_root/benchmark/integrative/scripts/run_synthetic_benchmark_slurm.sh" "$helper"
}

if [[ "$mode" == fixture ]]; then
    test -n "${SLURM_JOB_ID:-}"
    python3 "$repo_root/benchmark/integrative/scripts/prepare_synthetic_fixture.py" --truth "$truth" --truth-manifest "$truth_manifest" --output-dir "$fixture"
    exit 0
fi

if [[ "$mode" == evaluate-a || "$mode" == evaluate-b ]]; then
    test -n "${SLURM_JOB_ID:-}"
    run=${mode#evaluate-}
    python3 "$repo_root/benchmark/integrative/scripts/evaluate_synthetic_integration.py" --truth "$truth" --fixture "$fixture" --results-root "$results/run-$run" --output-dir "$metrics/run-$run"
    exit 0
fi

if [[ "$mode" == determinism ]]; then
    test -n "${SLURM_JOB_ID:-}"
    python3 "$repo_root/benchmark/integrative/scripts/compare_synthetic_runs.py" --run-a "$results/run-a" --run-b "$results/run-b" --output "$metrics/determinism_metrics.json"
    exit 0
fi

if [[ "$mode" == finalize ]]; then
    test -n "${SLURM_JOB_ID:-}"
    python3 "$repo_root/benchmark/integrative/scripts/finalize_synthetic_benchmark.py" \
        --execution-root "$scratch_root" --repo-root "$repo_root" \
        --output-dir "$repo_root/benchmark/integrative/results/synthetic" \
        --audit-archive "/home/ra236875@bio.ib.unicamp.br/helixforge-audits/helixforge-integrative-synthetic-10b-20260901.zip"
    exit 0
fi

if [[ "$mode" == validate ]]; then
    test -n "${SLURM_JOB_ID:-}"
    python3 -m unittest discover -s tests -p 'test_*.py'
    python3 "$repo_root/benchmark/integrative/scripts/validate_design.py"
    python3 -m py_compile "$repo_root"/benchmark/integrative/scripts/*.py
    exit 0
fi

[[ "$mode" == driver ]] || { echo "unsupported mode: $mode" >&2; exit 2; }
[[ -z "${SLURM_JOB_ID:-}" ]] || { echo "driver must run on the Slurm management node" >&2; exit 2; }
test -d "$repo_root/.git"
test -x "$java_bin"
test -s "$nextflow_jar"
test ! -e "$scratch_root"
mkdir -p "$scratch_root" "$results" "$metrics" "$logs" "$work" "$nxf_home"
git -C "$repo_root" rev-parse HEAD > "$scratch_root/repository_commit.txt"
git -C "$repo_root" status --porcelain=v1 > "$scratch_root/repository_status.txt"
sha256sum "$truth" "$truth_manifest" "$repo_root/benchmark/integrative/configs/synthetic_slurm.config" > "$scratch_root/frozen_input_checksums.txt"
printf 'hostname=%s\nos=%s\njava=%s\npython=%s\nnextflow_jar=%s\n' "$(hostname)" "$(uname -srmo)" "$($java_bin -version 2>&1 | head -1)" "$(python3 --version 2>&1)" "$nextflow_jar" > "$scratch_root/environment.txt"
submit_helper hf-int-fixture fixture

run_workflow() {
    local run=$1 out="$results/run-$1"
    env NXF_HOME="$nxf_home/run-$run" NXF_CACHE_DIR="$scratch_root/cache/run-$run" \
        "$java_bin" -Xms128m -Xmx1g -jar "$nextflow_jar" -log "$logs/run-$run.nextflow.log" \
        run "$repo_root/main.nf" -profile slurm -c "$repo_root/benchmark/integrative/configs/synthetic_slurm.config" \
        -ansi-log false -work-dir "$work/run-$run" -with-trace "$logs/run-$run.trace.tsv" \
        -with-report "$logs/run-$run.report.html" -with-timeline "$logs/run-$run.timeline.html" -with-dag "$logs/run-$run.dag.html" \
        --workflow integrative --outdir "$out" \
        --rna_manifest "$fixture/rna/rnaseq_run_manifest.json" --chip_manifest "$fixture/chip/chipseq_run_manifest.json" \
        --integrative_harmonization_policy "$fixture/harmonization_policy.json" \
        --integrative_prioritization_context "$fixture/prioritization_context.tsv" \
        --integrative_functional_annotation "$fixture/functional_annotation.tsv" \
        --integrative_report_title "HelixForge synthetic integration benchmark run $run"
}

run_workflow a
run_workflow b
submit_helper hf-int-eval-a evaluate-a
submit_helper hf-int-eval-b evaluate-b
submit_helper hf-int-determ determinism
sha256sum "$metrics/run-a"/* "$metrics/run-b"/* "$metrics/determinism_metrics.json" > "$metrics/SHA256SUMS"
echo "SYNTHETIC_INTEGRATION_EXECUTION=COMPLETE"
