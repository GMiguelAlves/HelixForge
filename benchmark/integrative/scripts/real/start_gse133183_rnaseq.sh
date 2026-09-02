#!/usr/bin/env bash
set -euo pipefail

repo=${1:-/home/ra236875@bio.ib.unicamp.br/helixforge-integrative-reentry-20260901}
root=${2:-/scratch/Schisto-epigenetics/gustavo/helixforge-integrative-real-20260901}
queue=${3:-general}
case_root="$root/cases/rnaseq"
test -s "$case_root/input_manifest.json"
test ! -e "$case_root/driver.pid"
mkdir -p "$case_root/logs"
nohup bash "$repo/benchmark/integrative/scripts/real/run_gse133183_rnaseq.sh" "$repo" "$root" "$queue" \
    > "$case_root/logs/driver.out" 2> "$case_root/logs/driver.err" < /dev/null &
pid=$!
printf '%s\n' "$pid" > "$case_root/driver.pid"
printf '%s\n' "$pid"
