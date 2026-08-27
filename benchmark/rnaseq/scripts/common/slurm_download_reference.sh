#!/usr/bin/env bash
set -euo pipefail

url=${1:?URL is required}
output=${2:?output path is required}
manifest=${3:?manifest path is required}
test -n "${SLURM_JOB_ID:-}"
test ! -e "$output"
mkdir -p "$(dirname "$output")" "$(dirname "$manifest")"
part="${output}.part.${SLURM_JOB_ID}"
test ! -e "$part"
cleanup() { rm -f -- "$part"; }
trap cleanup EXIT

start=$(date -u +%Y-%m-%dT%H:%M:%SZ)
if command -v curl >/dev/null 2>&1; then
    curl --fail --location --retry 4 --retry-delay 10 --output "$part" "$url"
else
    wget --tries=4 --waitretry=10 --output-document="$part" "$url"
fi
gzip -t "$part"
mv -- "$part" "$output"
trap - EXIT
checksum=$(sha256sum "$output" | awk '{print $1}')
bytes=$(stat -c '%s' "$output")
end=$(date -u +%Y-%m-%dT%H:%M:%SZ)
printf '{"status":"complete","slurm_job_id":"%s","node":"%s","url":"%s","path":"%s","bytes":%s,"sha256":"%s","started_utc":"%s","ended_utc":"%s"}\n' \
    "$SLURM_JOB_ID" "$(hostname)" "$url" "$output" "$bytes" "$checksum" "$start" "$end" > "$manifest"
