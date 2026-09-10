#!/usr/bin/env bash
set -euo pipefail

repo_root=${HF_REPO_ROOT:?HF_REPO_ROOT is required}
test -n "${SLURM_JOB_ID:-}"
cd "$repo_root"
python3 -m unittest discover -s tests/benchmark_integrative -p 'test_*.py'
