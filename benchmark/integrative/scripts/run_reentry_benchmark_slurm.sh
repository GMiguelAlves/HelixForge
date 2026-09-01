#!/usr/bin/env bash
set -euo pipefail

repo_root=${HELIXFORGE_REPO_ROOT:?HELIXFORGE_REPO_ROOT is required}
scratch_root=${HELIXFORGE_BENCHMARK_ROOT:?HELIXFORGE_BENCHMARK_ROOT is required}
queue=${HELIXFORGE_SLURM_QUEUE:-general}
conda_root=${HELIXFORGE_CONDA_ROOT:-/home/ra236875@bio.ib.unicamp.br/miniconda3}
java_bin=${HELIXFORGE_JAVA:-${conda_root}/envs/rna-tools/bin/java}
contract_python=${HELIXFORGE_CONTRACT_PYTHON:-${conda_root}/envs/rna-tools/bin/python}
nextflow_jar=${HELIXFORGE_NEXTFLOW_JAR:-/home/ra236875@bio.ib.unicamp.br/helixforge-validation-20260811/.validation-runtimes/nxf-home-25.10.7/framework/25.10.7/nextflow-25.10.7-one.jar}
baseline_audit=${HELIXFORGE_10B_AUDIT:-/home/ra236875@bio.ib.unicamp.br/helixforge-audits/helixforge-integrative-synthetic-10b-20260901.zip}
mode=${1:-driver}

case "$scratch_root" in
    /scratch/Schisto-epigenetics/gustavo/helixforge-integrative-reentry-*) ;;
    *) echo "Refusing unexpected benchmark root: $scratch_root" >&2; exit 2 ;;
esac

direct="$scratch_root/direct_bundle"
relocated="$scratch_root/relocated_bundle"
results="$scratch_root/results"
logs="$scratch_root/logs"
work="$scratch_root/work"
cache="$scratch_root/cache"
nxf_home="$scratch_root/nxf-home"
setup="$scratch_root/setup"
public_results="$repo_root/benchmark/integrative/results/reentry"
public_report="$repo_root/benchmark/integrative/reports/reentry_equivalence_benchmark.md"
audit_archive="/home/ra236875@bio.ib.unicamp.br/helixforge-audits/helixforge-integrative-reentry-10c-20260901.zip"

submit_helper() {
    local name=$1 helper=$2
    sbatch --wait --parsable --job-name="$name" --partition="$queue" --cpus-per-task=1 --mem=2G --time=00:20:00 \
        --chdir="$repo_root" --export="ALL,HELIXFORGE_REPO_ROOT=$repo_root,HELIXFORGE_BENCHMARK_ROOT=$scratch_root,HELIXFORGE_SLURM_QUEUE=$queue,HELIXFORGE_CONDA_ROOT=$conda_root,HELIXFORGE_JAVA=$java_bin,HELIXFORGE_NEXTFLOW_JAR=$nextflow_jar,HELIXFORGE_10B_AUDIT=$baseline_audit" \
        --output="$logs/${name}-%j.out" "$repo_root/benchmark/integrative/scripts/run_reentry_benchmark_slurm.sh" "$helper"
}

if [[ "$mode" == setup ]]; then
    test -n "${SLURM_JOB_ID:-}"
    python3 "$repo_root/benchmark/integrative/scripts/prepare_synthetic_fixture.py" \
        --truth "$repo_root/benchmark/integrative/datasets/synthetic_truth.tsv" \
        --truth-manifest "$repo_root/benchmark/integrative/datasets/synthetic_truth_manifest.json" \
        --output-dir "$direct"
    "$contract_python" "$repo_root/benchmark/integrative/scripts/prepare_reentry_fixture.py" \
        --repo-root "$repo_root" --direct-root "$direct" --reentry-root "$relocated" \
        --baseline-audit "$baseline_audit" --output-dir "$setup"
    exit 0
fi

if [[ "$mode" == isolate ]]; then
    test -n "${SLURM_JOB_ID:-}"
    test "$work/route-a" != "$work/route-b"
    python3 -c "from pathlib import Path; import json; roots=[Path('$work/route-a'),Path('$cache/route-a'),Path('$nxf_home/route-a')]; print(json.dumps({'removed_state_bytes':sum(p.stat().st_size for r in roots if r.exists() for p in r.rglob('*') if p.is_file()),'route_a_results_preserved':Path('$results/route-a').is_dir(),'relocated_bundle_ready':Path('$relocated/rna/rnaseq_run_manifest.json').is_file()}))" > "$setup/isolation.json"
    rm -rf -- "$work/route-a" "$cache/route-a" "$nxf_home/route-a"
    test ! -e "$work/route-a"
    test ! -e "$cache/route-a"
    test ! -e "$nxf_home/route-a"
    exit 0
fi

if [[ "$mode" == compare ]]; then
    test -n "${SLURM_JOB_ID:-}"
    python3 "$repo_root/benchmark/integrative/scripts/compare_reentry_routes.py" \
        --execution-root "$scratch_root" \
        --baseline-summary "$repo_root/benchmark/integrative/results/synthetic/benchmark_summary.json" \
        --output-dir "$public_results" --report "$public_report"
    exit 0
fi

if [[ "$mode" == finalize ]]; then
    test -n "${SLURM_JOB_ID:-}"
    python3 "$repo_root/benchmark/integrative/scripts/finalize_reentry_benchmark.py" \
        --execution-root "$scratch_root" --repo-root "$repo_root" --output-dir "$public_results" \
        --report "$public_report" --audit-archive "$audit_archive"
    exit 0
fi

if [[ "$mode" == validate ]]; then
    test -n "${SLURM_JOB_ID:-}"
    python3 -m unittest discover -s tests -p 'test_*.py'
    python3 "$repo_root/benchmark/integrative/scripts/validate_design.py"
    python3 "$repo_root/benchmark/integrative/scripts/validate_reentry_results.py" --results "$public_results" --report "$public_report"
    python3 -m py_compile "$repo_root"/benchmark/integrative/scripts/*.py
    exit 0
fi

[[ "$mode" == driver ]] || { echo "unsupported mode: $mode" >&2; exit 2; }
[[ -z "${SLURM_JOB_ID:-}" ]] || { echo "driver must run on the Slurm management node" >&2; exit 2; }
test -d "$repo_root/.git"
test -x "$java_bin"
test -x "$contract_python"
test -s "$nextflow_jar"
test -s "$baseline_audit"
test ! -e "$scratch_root"
mkdir -p "$scratch_root" "$results" "$logs" "$work" "$cache" "$nxf_home" "$setup"
git -C "$repo_root" rev-parse HEAD > "$scratch_root/repository_commit.txt"
git -C "$repo_root" status --porcelain=v1 > "$scratch_root/repository_status.txt"
printf 'hostname=%s\nos=%s\njava=%s\npython=%s\ncontract_python=%s\nnextflow_jar=%s\n' "$(hostname)" "$(uname -srmo)" "$($java_bin -version 2>&1 | head -1)" "$(python3 --version 2>&1)" "$($contract_python --version 2>&1)" "$nextflow_jar" > "$scratch_root/environment.txt"
printf '%s\n' \
    'Route A: nextflow run main.nf --workflow integrative with direct frozen terminal manifests' \
    'Route B: nextflow run main.nf --workflow integrative with relocated manifest_relative terminal bundles' \
    'Both routes: profile slurm; Nextflow 25.10.7; independent work/cache/NXF_HOME; identical policies and report title' \
    > "$scratch_root/commands.txt"
submit_helper hf-ir-setup setup

run_workflow() {
    local route=$1 bundle=$2 out="$results/route-$1"
    env NXF_HOME="$nxf_home/route-$route" NXF_CACHE_DIR="$cache/route-$route" \
        "$java_bin" -Xms128m -Xmx1g -jar "$nextflow_jar" -log "$logs/route-$route.nextflow.log" \
        run "$repo_root/main.nf" -profile slurm -c "$repo_root/benchmark/integrative/configs/reentry_slurm.config" \
        -ansi-log false -work-dir "$work/route-$route" -with-trace "$logs/route-$route.trace.tsv" \
        -with-report "$logs/route-$route.report.html" -with-timeline "$logs/route-$route.timeline.html" -with-dag "$logs/route-$route.dag.html" \
        --workflow integrative --outdir "$out" \
        --rna_manifest "$bundle/rna/rnaseq_run_manifest.json" --chip_manifest "$bundle/chip/chipseq_run_manifest.json" \
        --integrative_harmonization_policy "$bundle/harmonization_policy.json" \
        --integrative_prioritization_context "$bundle/prioritization_context.tsv" \
        --integrative_functional_annotation "$bundle/functional_annotation.tsv" \
        --integrative_report_title "HelixForge manifest re-entry equivalence benchmark"
}

run_workflow a "$direct"
submit_helper hf-ir-isolate isolate
run_workflow b "$relocated"
submit_helper hf-ir-compare compare
submit_helper hf-ir-final finalize
submit_helper hf-ir-valid validate
echo "MANIFEST_REENTRY_EXECUTION=COMPLETE"
