#!/usr/bin/env bash
set -euo pipefail

registry=${1:?reference registry TSV is required}
python_bin=${2:?Python executable is required}
builder=${3:?reference builder is required}
reference_root=${4:?reference output root is required}
test -n "${SLURM_JOB_ID:-}"
test -s "$registry"
test -x "$python_bin"
test -f "$builder"

sources="$reference_root/sources"
bundle="$reference_root/gencode49-primary"
manifest="$reference_root/reference_manifest.json"
md5s="$sources/MD5SUMS"
mkdir -p "$sources"

if [[ -s "$manifest" ]]; then
    "$python_bin" "$builder" --manifest "$manifest" --validate-existing
    exit 0
fi
test ! -e "$bundle"

download() {
    local url=$1 destination=$2 expected_md5=${3:-}
    if [[ -f "$destination" ]]; then
        if [[ -n "$expected_md5" ]]; then
            [[ "$(md5sum "$destination" | awk '{print $1}')" == "$expected_md5" ]]
        fi
        return
    fi
    local partial="${destination}.part"
    curl --fail --location --retry 10 --retry-delay 15 --retry-all-errors \
        --continue-at - --output "$partial" "$url"
    if [[ -n "$expected_md5" ]]; then
        [[ "$(md5sum "$partial" | awk '{print $1}')" == "$expected_md5" ]]
    fi
    mv -- "$partial" "$destination"
}

download \
    https://ftp.ebi.ac.uk/pub/databases/gencode/Gencode_human/release_49/MD5SUMS \
    "$md5s"

while IFS=$'\t' read -r bundle_id release assembly role filename url checksum_source derivation; do
    [[ "$bundle_id" == bundle_id ]] && continue
    [[ "$bundle_id" == gencode_human_v49_primary ]]
    [[ "$release" == GENCODE_49 ]]
    [[ "$assembly" == GRCh38.p14 ]]
    [[ "$checksum_source" == "release_49 MD5SUMS" ]]
    expected_md5=$(awk -v filename="$filename" '$2 == filename {print $1}' "$md5s")
    [[ "$expected_md5" =~ ^[0-9a-f]{32}$ ]]
    download "$url" "$sources/$filename" "$expected_md5"
    gzip -t "$sources/$filename"
done < "$registry"

stage=$(mktemp -d "$reference_root/.gencode49-build.XXXXXX")
cleanup() { rm -rf -- "$stage"; }
trap cleanup EXIT
"$python_bin" "$builder" \
    --registry "$registry" \
    --sources-dir "$sources" \
    --md5s "$md5s" \
    --output-dir "$stage/bundle" \
    --published-dir "$bundle" \
    --manifest "$stage/reference_manifest.json"
mv -- "$stage/bundle" "$bundle"
mv -- "$stage/reference_manifest.json" "$manifest"
trap - EXIT
rmdir -- "$stage"
