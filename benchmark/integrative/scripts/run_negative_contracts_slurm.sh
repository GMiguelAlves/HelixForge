#!/usr/bin/env bash
set -euo pipefail

repo_root=${HELIXFORGE_REPO_ROOT:?HELIXFORGE_REPO_ROOT is required}
scratch_root=${HELIXFORGE_BENCHMARK_ROOT:?HELIXFORGE_BENCHMARK_ROOT is required}
queue=${HELIXFORGE_SLURM_QUEUE:-general}
python_bin=${HELIXFORGE_PYTHON:-/home/ra236875@bio.ib.unicamp.br/miniconda3/envs/rna-tools/bin/python}
audit_archive=${HELIXFORGE_AUDIT_ARCHIVE:-/home/ra236875@bio.ib.unicamp.br/helixforge-audits/helixforge-integrative-negative-contracts-10e-20260901.zip}
mode=${1:-driver}

case "$scratch_root" in
    /scratch/Schisto-epigenetics/gustavo/helixforge-integrative-contracts-*) ;;
    *) echo "Refusing unexpected benchmark root: $scratch_root" >&2; exit 2 ;;
esac

if [[ "$mode" == execute ]]; then
    test -n "${SLURM_JOB_ID:-}"
    "$python_bin" "$repo_root/benchmark/integrative/scripts/execute_negative_contract_validation.py" \
        --work-root "$scratch_root/execution" \
        --output-dir "$scratch_root/results/contracts" \
        --report-path "$scratch_root/results/negative_contract_validation.md" \
        --audit-archive "$audit_archive"
    exit 0
fi

if [[ "$mode" == validate ]]; then
    test -n "${SLURM_JOB_ID:-}"
    "$python_bin" -m unittest discover -s tests -p 'test_*.py'
    "$python_bin" "$repo_root/benchmark/integrative/scripts/validate_design.py"
    "$python_bin" -m py_compile "$repo_root"/benchmark/integrative/scripts/*.py
    exit 0
fi

[[ "$mode" == driver ]] || { echo "unsupported mode: $mode" >&2; exit 2; }
[[ -z "${SLURM_JOB_ID:-}" ]] || { echo "driver must run on the Slurm management node" >&2; exit 2; }
test -d "$repo_root/.git"
test -x "$python_bin"
test ! -e "$scratch_root"
mkdir -p "$scratch_root/logs" "$scratch_root/results"
git -C "$repo_root" rev-parse HEAD > "$scratch_root/repository_commit.txt"
git -C "$repo_root" status --porcelain=v1 > "$scratch_root/repository_status.txt"
sha256sum "$repo_root/benchmark/integrative/datasets/negative_contract_cases.tsv" > "$scratch_root/frozen_input_checksums.txt"
printf 'hostname=%s\nos=%s\npython=%s\n' "$(hostname)" "$(uname -srmo)" "$($python_bin --version 2>&1)" > "$scratch_root/environment.txt"

sbatch --wait --parsable --job-name=hf-int-contracts --partition="$queue" --cpus-per-task=1 --mem=4G --time=00:20:00 \
    --chdir="$repo_root" \
    --export="ALL,HELIXFORGE_REPO_ROOT=$repo_root,HELIXFORGE_BENCHMARK_ROOT=$scratch_root,HELIXFORGE_SLURM_QUEUE=$queue,HELIXFORGE_PYTHON=$python_bin,HELIXFORGE_AUDIT_ARCHIVE=$audit_archive" \
    --output="$scratch_root/logs/hf-int-contracts-%j.out" \
    "$repo_root/benchmark/integrative/scripts/run_negative_contracts_slurm.sh" execute

sbatch --wait --parsable --job-name=hf-int-contract-tests --partition="$queue" --cpus-per-task=1 --mem=4G --time=00:20:00 \
    --chdir="$repo_root" \
    --export="ALL,HELIXFORGE_REPO_ROOT=$repo_root,HELIXFORGE_BENCHMARK_ROOT=$scratch_root,HELIXFORGE_SLURM_QUEUE=$queue,HELIXFORGE_PYTHON=$python_bin" \
    --output="$scratch_root/logs/hf-int-contract-tests-%j.out" \
    "$repo_root/benchmark/integrative/scripts/run_negative_contracts_slurm.sh" validate

echo "NEGATIVE_CONTRACT_VALIDATION=COMPLETE"
