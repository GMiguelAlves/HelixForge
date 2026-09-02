#!/usr/bin/env bash
set -euo pipefail

repo_root=${HF_REPO_ROOT:?HF_REPO_ROOT is required}
scratch_root=${HF_SCRATCH_ROOT:?HF_SCRATCH_ROOT is required}
python_bin=${HF_PYTHON_BIN:-python3}
samtools=${HF_SAMTOOLS:?HF_SAMTOOLS is required}
reference_root="$scratch_root/reference"
sources="$reference_root/sources"
bundle="$reference_root/bundle"
manifest="$reference_root/reference_manifest.json"
registry="$repo_root/benchmark/integrative/datasets/reference_sources.tsv"
updater="$repo_root/benchmark/integrative/scripts/real/update_real_benchmark_state.py"
builder="$repo_root/benchmark/integrative/scripts/real/prepare_gse133183_reference.py"
test -n "${SLURM_JOB_ID:-}"
case "$scratch_root" in
    /scratch/Schisto-epigenetics/gustavo/helixforge-integrative-real-*) ;;
    *) echo "unsafe scratch root: $scratch_root" >&2; exit 2 ;;
esac
test ! -e "$bundle"
test ! -e "$manifest"
mkdir -p "$sources"
export HF_STATE_TIME_UTC
HF_STATE_TIME_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)
"$python_bin" "$updater" --state "$scratch_root/benchmark_state.json" \
    --phase REFERENCE_SUBMITTED --status RUNNING --job-id "$SLURM_JOB_ID" \
    --job-kind reference_preparation --workdir "$reference_root"

mark_failed() {
    local code=$?
    HF_STATE_TIME_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ) \
        "$python_bin" "$updater" --state "$scratch_root/benchmark_state.json" \
        --phase REFERENCE_FAILED --status FAILED --job-id "$SLURM_JOB_ID" \
        --job-kind reference_preparation --workdir "$reference_root" || true
    exit "$code"
}
trap mark_failed ERR

download_one() {
    local url=$1 destination=$2 expected_md5=$3
    if [[ -f "$destination" ]]; then
        printf '%s  %s\n' "$expected_md5" "$destination" | md5sum -c -
        gzip -t "$destination"
        return
    fi
    local partial="${destination}.part"
    curl --fail --location --retry 10 --retry-delay 20 --retry-all-errors \
        --continue-at - --output "$partial" "$url"
    printf '%s  %s\n' "$expected_md5" "$partial" | md5sum -c -
    gzip -t "$partial"
    mv -- "$partial" "$destination"
}

while IFS=$'\t' read -r role provider release filename assembly md5 url status; do
    [[ "$role" == role ]] && continue
    [[ "$md5" =~ ^[0-9a-f]{32}$ ]]
    download_one "$url" "$sources/$filename" "$md5"
done < "$registry"

"$python_bin" "$builder" --registry "$registry" --sources-dir "$sources" \
    --output-dir "$bundle" --manifest "$manifest" --samtools "$samtools"
HF_STATE_TIME_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)
"$python_bin" "$updater" --state "$scratch_root/benchmark_state.json" \
    --phase REFERENCE_COMPLETE --status COMPLETE --job-id "$SLURM_JOB_ID" \
    --job-kind reference_preparation --workdir "$reference_root" \
    --expected-output reference/reference_manifest.json
trap - ERR
