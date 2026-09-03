#!/usr/bin/env bash
set -euo pipefail

repo=${1:-/home/ra236875@bio.ib.unicamp.br/helixforge-integrative-post-qc-20260902}
root=${2:-/scratch/Schisto-epigenetics/gustavo/helixforge-integrative-real-20260901}
queue=${3:-general}
case_root="$root/cases/rnaseq"
pid_file="$case_root/report_reentry_driver.pid"

if [[ -e "$pid_file" ]]; then
    old_pid=$(cat "$pid_file")
    if kill -0 "$old_pid" 2>/dev/null; then
        echo "RNA-seq report re-entry driver is already running: $old_pid" >&2
        exit 2
    fi
    rm -f "$pid_file"
fi

mkdir -p "$case_root/logs/report_reentry"
nohup bash "$repo/benchmark/integrative/scripts/real/run_gse133183_rnaseq_report_reentry.sh" \
    "$repo" "$root" "$queue" \
    > "$case_root/logs/report_reentry/driver.out" \
    2> "$case_root/logs/report_reentry/driver.err" < /dev/null &
pid=$!
printf '%s\n' "$pid" > "$pid_file"
printf '%s\n' "$pid"
