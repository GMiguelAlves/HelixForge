#!/usr/bin/env bash
set -euo pipefail

output_dir=${1:?output directory is required}
conda_base=${2:?conda base is required}
java21=${3:?Java 21 executable is required}
rna_env=${4:-$conda_base/envs/rna-tools}
r_env=${5:-$conda_base/envs/r-analysis}
python_env=${6:-$conda_base/envs/python-list}
mkdir -p "$output_dir"
test -n "${SLURM_JOB_ID:-}"

export PATH="$(dirname "$java21"):$rna_env/bin:$r_env/bin:$python_env/bin:/usr/bin:/bin"

{
    printf 'utc\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf 'slurm_job_id\t%s\n' "$SLURM_JOB_ID"
    printf 'node\t%s\n' "$(hostname)"
    printf 'kernel\t%s\n' "$(uname -srmo)"
    printf 'cpus_allocated\t%s\n' "${SLURM_CPUS_PER_TASK:-unknown}"
    printf 'memory_per_node\t%s\n' "${SLURM_MEM_PER_NODE:-unknown}"
    printf 'home_filesystem\t%s\n' "$(stat -f -c '%T' "$HOME")"
    printf 'output_filesystem\t%s\n' "$(stat -f -c '%T' "$output_dir")"
} > "$output_dir/environment.tsv"

{
    "$java21" -version
    "$rna_env/bin/salmon" --version
    "$rna_env/bin/fastqc" --version
    "$rna_env/bin/trim_galore" --version
    "$rna_env/bin/multiqc" --version
    "$python_env/bin/python3" --version
    "$r_env/bin/Rscript" -e 'cat("R ", as.character(getRversion()), "\n", sep=""); cat("tximport ", as.character(packageVersion("tximport")), "\n", sep=""); cat("DESeq2 ", as.character(packageVersion("DESeq2")), "\n", sep="")'
    if "$r_env/bin/Rscript" -e 'quit(status=ifelse(requireNamespace("polyester", quietly=TRUE), 0, 1))'; then
        "$r_env/bin/Rscript" -e 'cat("polyester ", as.character(packageVersion("polyester")), "\n", sep="")'
    else
        printf 'polyester MISSING\n'
    fi
} > "$output_dir/tool_versions.txt" 2>&1

for executable in \
    "$java21" "$rna_env/bin/salmon" "$rna_env/bin/fastqc" \
    "$rna_env/bin/trim_galore" "$rna_env/bin/multiqc" \
    "$python_env/bin/python3" "$r_env/bin/Rscript"; do
    test -x "$executable"
done

printf '{"status":"complete","slurm_job_id":"%s","node":"%s"}\n' \
    "$SLURM_JOB_ID" "$(hostname)" > "$output_dir/preflight.json"
