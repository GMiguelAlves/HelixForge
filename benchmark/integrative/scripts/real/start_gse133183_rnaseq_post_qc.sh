#!/usr/bin/env bash
set -euo pipefail

repo=${1:-/home/ra236875@bio.ib.unicamp.br/helixforge-integrative-reentry-20260901}
root=${2:-/scratch/Schisto-epigenetics/gustavo/helixforge-integrative-real-20260901}
queue=${3:-general}
case_root="$root/cases/rnaseq"
pid_file="$case_root/post_qc_driver.pid"

if [[ -e "$pid_file" ]]; then
    old_pid=$(cat "$pid_file")
    if kill -0 "$old_pid" 2>/dev/null; then
        echo "RNA-seq post-QC driver is already running: $old_pid" >&2
        exit 2
    fi
    rm -f "$pid_file"
fi

mkdir -p "$case_root/logs/post_qc"
nohup bash "$repo/benchmark/integrative/scripts/real/run_gse133183_rnaseq_post_qc.sh" \
    "$repo" "$root" "$queue" \
    > "$case_root/logs/post_qc/driver.out" \
    2> "$case_root/logs/post_qc/driver.err" < /dev/null &
pid=$!
printf '%s\n' "$pid" > "$pid_file"
printf '%s\n' "$pid"
