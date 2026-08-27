#!/usr/bin/env bash
set -euo pipefail

settings=${1:?user settings file is required}
current_prefix=${2:?current Python prefix is required}
provider_prefix=${3:?replacement Python prefix is required}
output=${4:?audit manifest is required}

test -n "${SLURM_JOB_ID:-}"
test -s "$settings"
test -x "$provider_prefix/bin/python"
grep -Fxq "export PYTHON_ENV=$current_prefix" "$settings"

python_version=$($provider_prefix/bin/python -c 'import platform; print(platform.python_version())')
pandas_version=$($provider_prefix/bin/python -c 'import pandas; print(pandas.__version__)')
[[ -n "$python_version" && -n "$pandas_version" ]]

sed -i \
    "s|^export PYTHON_ENV=$current_prefix$|export PYTHON_ENV=$provider_prefix|" \
    "$settings"
grep -Fxq "export PYTHON_ENV=$provider_prefix" "$settings"

settings_sha256=$(sha256sum "$settings" | awk '{print $1}')
printf '{"status":"complete","slurm_job_id":"%s","node":"%s","settings":"%s","settings_sha256":"%s","provider_prefix":"%s","python":"%s","pandas":"%s","reason":"generate_salmon_plan.py requires pandas"}\n' \
    "$SLURM_JOB_ID" "$(hostname)" "$settings" "$settings_sha256" \
    "$provider_prefix" "$python_version" "$pandas_version" > "$output"
