#!/usr/bin/env bash
set -euo pipefail

repo=${1:-/home/CLUSTER_USER/helixforge-integrative-sanitized}
root=${2:-/scratch/HELIXFORGE_WORKSPACE/helixforge-integrative-real}
queue=${3:-general}
case_root="$root/cases/chipseq_h3k27me3"
pid_file="$case_root/completion_reentry_driver.pid"
if [[ -e "$pid_file" ]]; then
    old_pid=$(cat "$pid_file")
    if kill -0 "$old_pid" 2>/dev/null; then
        echo "H3K27me3 completion re-entry is already running: $old_pid" >&2
        exit 2
    fi
    rm -f "$pid_file"
fi
mkdir -p "$case_root/logs/completion_reentry"
nohup bash "$repo/benchmark/integrative/scripts/real/run_gse133183_h3k27me3_completion_reentry.sh" \
    "$repo" "$root" "$queue" \
    > "$case_root/logs/completion_reentry/driver.out" \
    2> "$case_root/logs/completion_reentry/driver.err" < /dev/null &
pid=$!
printf '%s\n' "$pid" > "$pid_file"
printf '%s\n' "$pid"
