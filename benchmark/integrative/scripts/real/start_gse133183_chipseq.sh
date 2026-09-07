#!/usr/bin/env bash
set -euo pipefail

repo=${1:-/home/CLUSTER_USER/helixforge-integrative-reentry-20260901}
root=${2:-/scratch/HELIXFORGE_WORKSPACE/helixforge-integrative-real-20260901}
mark=${3:?mark is required: H3K27me3 or H3K27ac}
queue=${4:-general}
run_mode=${5:-fresh}
attempt_label=${6:-initial}
case "$mark" in
    H3K27me3) case_name=chipseq_h3k27me3 ;;
    H3K27ac) case_name=chipseq_h3k27ac ;;
    *) echo "unsupported mark: $mark" >&2; exit 2 ;;
esac

case_root="$root/cases/$case_name"
test -s "$case_root/input_manifest.json"
pid_file="$case_root/driver.pid"
if [[ -e "$pid_file" ]]; then
    old_pid=$(cat "$pid_file")
    if kill -0 "$old_pid" 2>/dev/null; then
        echo "$mark driver is already running: $old_pid" >&2
        exit 2
    fi
    rm -f "$pid_file"
fi

mkdir -p "$case_root/logs"
if [[ "$run_mode" == resume ]]; then
    archive="$case_root/logs/attempts/$(date -u +%Y%m%dT%H%M%SZ)-${attempt_label}"
    mkdir -p "$archive"
    for name in nextflow.log driver.out driver.err; do
        [[ ! -e "$case_root/logs/$name" ]] || cp "$case_root/logs/$name" "$archive/$name"
    done
fi

nohup bash "$repo/benchmark/integrative/scripts/real/run_gse133183_chipseq.sh" \
    "$repo" "$root" "$mark" "$queue" "$run_mode" "$attempt_label" \
    > "$case_root/logs/driver.out" 2> "$case_root/logs/driver.err" < /dev/null &
pid=$!
printf '%s\n' "$pid" > "$pid_file"
printf '%s\n' "$pid"
