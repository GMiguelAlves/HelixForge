#!/usr/bin/env bash
set -euo pipefail

settings=${1:?user settings file is required}
rna_env=${2:?RNA tools prefix is required}
python_env=${3:?Python prefix is required}
r_env=${4:?R analysis prefix is required}
output=${5:?audit manifest is required}

test -n "${SLURM_JOB_ID:-}"
test -s "$settings"
test -x "$rna_env/bin/salmon"
test -x "$python_env/bin/python3"
test -x "$r_env/bin/Rscript"
grep -Fxq 'export RNA_TOOLS_ENV=rna-tools-rc' "$settings"
grep -Fxq 'export PYTHON_ENV=python-runtime-rc' "$settings"
grep -Fxq 'export R_ANALYSIS_ENV=r-analysis-rc' "$settings"

sed -i \
    -e "s|^export RNA_TOOLS_ENV=rna-tools-rc$|export RNA_TOOLS_ENV=$rna_env|" \
    -e "s|^export PYTHON_ENV=python-runtime-rc$|export PYTHON_ENV=$python_env|" \
    -e "s|^export R_ANALYSIS_ENV=r-analysis-rc$|export R_ANALYSIS_ENV=$r_env|" \
    "$settings"

grep -Fxq "export RNA_TOOLS_ENV=$rna_env" "$settings"
grep -Fxq "export PYTHON_ENV=$python_env" "$settings"
grep -Fxq "export R_ANALYSIS_ENV=$r_env" "$settings"
settings_sha256=$(sha256sum "$settings" | awk '{print $1}')
printf '{"status":"complete","slurm_job_id":"%s","node":"%s","settings":"%s","settings_sha256":"%s","rna_env":"%s","python_env":"%s","r_env":"%s"}\n' \
    "$SLURM_JOB_ID" "$(hostname)" "$settings" "$settings_sha256" \
    "$rna_env" "$python_env" "$r_env" > "$output"
