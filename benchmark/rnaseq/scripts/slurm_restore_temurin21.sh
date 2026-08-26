#!/usr/bin/env bash
set -euo pipefail

runtime_root=${1:?runtime output root is required}
test -n "${SLURM_JOB_ID:-}"

version=21.0.12+8
archive=OpenJDK21U-jdk_x64_linux_hotspot_21.0.12_8.tar.gz
url="https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.12%2B8/$archive"
expected_sha256=e4446ff06a276155697597cc0f1b15da004ff083f4964a35271ecee567177370
sources="$runtime_root/sources"
prefix="$runtime_root/temurin-21.0.12+8"
manifest="$runtime_root/temurin-21.0.12+8.manifest.json"

validate_java() {
    local java_bin=$1
    test -x "$java_bin"
    "$java_bin" -version 2>&1 | grep -Fq 'openjdk version "21.0.12"'
    "$java_bin" -version 2>&1 | grep -Fq 'Temurin-21.0.12+8'
}

if [[ -s "$manifest" ]]; then
    validate_java "$prefix/bin/java"
    grep -Fq "\"sha256\":\"$expected_sha256\"" "$manifest"
    printf '{"status":"RUNTIME_READY","version":"%s","path":"%s"}\n' "$version" "$prefix/bin/java"
    exit 0
fi
test ! -e "$prefix"
mkdir -p "$sources"
payload="$sources/$archive"
if [[ ! -f "$payload" ]]; then
    curl --fail --location --retry 10 --retry-delay 15 --retry-all-errors \
        --continue-at - --output "$payload.part" "$url"
    [[ "$(sha256sum "$payload.part" | awk '{print $1}')" == "$expected_sha256" ]]
    mv -- "$payload.part" "$payload"
fi
[[ "$(sha256sum "$payload" | awk '{print $1}')" == "$expected_sha256" ]]

stage=$(mktemp -d "$runtime_root/.temurin21.XXXXXX")
cleanup() { rm -rf -- "$stage"; }
trap cleanup EXIT
tar -xzf "$payload" --strip-components=1 -C "$stage"
validate_java "$stage/bin/java"
mv -- "$stage" "$prefix"
trap - EXIT

bytes=$(stat -c '%s' "$payload")
printf '{"schema_version":"1.0","status":"RUNTIME_READY","provider":"Eclipse Temurin","version":"%s","archive":"%s","url":"%s","bytes":%s,"sha256":"%s","java":"%s","slurm_job_id":"%s"}\n' \
    "$version" "$archive" "$url" "$bytes" "$expected_sha256" "$prefix/bin/java" "$SLURM_JOB_ID" > "$manifest"
validate_java "$prefix/bin/java"
