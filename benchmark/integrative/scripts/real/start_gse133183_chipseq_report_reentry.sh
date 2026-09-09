#!/usr/bin/env bash
set -euo pipefail

repo=${1:-/home/CLUSTER_USER/helixforge-integrative-sanitized}
root=${2:-/scratch/HELIXFORGE_WORKSPACE/helixforge-integrative-real}
mark=${3:?mark is required}
queue=${4:-general}
inventory=${5:?report inventory is required}
case "$mark" in
    H3K27ac) case_name=chipseq_h3k27ac ;;
    H3K27me3) case_name=chipseq_h3k27me3 ;;
    *) echo "unsupported mark: $mark" >&2; exit 2 ;;
esac
case_root="$root/cases/$case_name"
pid_file="$case_root/report_reentry_driver.pid"
if [[ -e "$pid_file" ]]; then
    old_pid=$(cat "$pid_file")
    if kill -0 "$old_pid" 2>/dev/null; then
        echo "report re-entry is already running: $old_pid" >&2
        exit 2
    fi
    rm -f "$pid_file"
fi
mkdir -p "$case_root/logs/report_reentry"
if [[ -e "$case_root/logs/report_reentry/driver.out" || -e "$case_root/logs/report_reentry/driver.err" ]]; then
    archive="$case_root/logs/report_reentry/attempts/$(date -u +%Y%m%dT%H%M%SZ)"
    mkdir -p "$archive"
    for name in driver.out driver.err nextflow.log; do
        [[ ! -e "$case_root/logs/report_reentry/$name" ]] || cp "$case_root/logs/report_reentry/$name" "$archive/$name"
    done
fi
nohup bash "$repo/benchmark/integrative/scripts/real/run_gse133183_chipseq_report_reentry.sh" \
    "$repo" "$root" "$mark" "$queue" "$inventory" \
    > "$case_root/logs/report_reentry/driver.out" \
    2> "$case_root/logs/report_reentry/driver.err" < /dev/null &
pid=$!
printf '%s\n' "$pid" > "$pid_file"
printf '%s\n' "$pid"
