#!/usr/bin/env bash
set -euo pipefail

repo=${1:-/home/ra236875@bio.ib.unicamp.br/helixforge-integrative-reentry-20260901}
root=${2:-/scratch/Schisto-epigenetics/gustavo/helixforge-integrative-real-20260901}
queue=${3:-general}
run_mode=${4:-fresh}
case_root="$root/cases/rnaseq"
test -s "$case_root/input_manifest.json"
if [[ -e "$case_root/driver.pid" ]]; then
    old_pid=$(cat "$case_root/driver.pid")
    if kill -0 "$old_pid" 2>/dev/null; then
        echo "RNA-seq driver is already running: $old_pid" >&2
        exit 2
    fi
    rm -f "$case_root/driver.pid"
fi
mkdir -p "$case_root/logs"
if [[ "$run_mode" == resume ]]; then
    test -s "$case_root/runtime_correction.json"
    for name in nextflow.log driver.out driver.err; do
        if [[ -s "$case_root/logs/$name" && ! -e "$case_root/logs/initial_failed.$name" ]]; then
            cp "$case_root/logs/$name" "$case_root/logs/initial_failed.$name"
        fi
    done
fi
nohup bash "$repo/benchmark/integrative/scripts/real/run_gse133183_rnaseq.sh" "$repo" "$root" "$queue" "$run_mode" \
    > "$case_root/logs/driver.out" 2> "$case_root/logs/driver.err" < /dev/null &
pid=$!
printf '%s\n' "$pid" > "$case_root/driver.pid"
printf '%s\n' "$pid"
