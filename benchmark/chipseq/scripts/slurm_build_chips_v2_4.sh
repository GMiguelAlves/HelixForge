#!/usr/bin/env bash

set -euo pipefail

source_tar=${1:?ChIPs v2.4 source archive is required}
install_root=${2:?installation root is required}
expected_source_sha256=${3:?expected source SHA-256 is required}

expected_commit=766c92cbb50783a537c897431b77e6bff8dba506
observed_source_sha256=$(sha256sum "$source_tar" | cut -d' ' -f1)
[[ "$observed_source_sha256" == "$expected_source_sha256" ]] || {
    echo "ChIPs source checksum mismatch" >&2
    exit 2
}

[[ -n "${SLURM_JOB_ID:-}" ]] || {
    echo "ChIPs must be built inside a Slurm allocation." >&2
    exit 2
}
[[ ! -e "$install_root" ]] || {
    echo "Refusing to overwrite existing ChIPs installation: $install_root" >&2
    exit 2
}

build_parent=$(mktemp -d "${TMPDIR:-/tmp}/helixforge-chips-v2.4.XXXXXX")
trap 'rm -rf "$build_parent"' EXIT
tar -xzf "$source_tar" -C "$build_parent"
source_root=$(find "$build_parent" -mindepth 2 -maxdepth 2 -type f -name CMakeLists.txt -printf '%h\n' | head -n 1)
[[ -n "$source_root" ]]
compiler=${CXX:-c++}

cmake -S "$source_root" -B "$build_parent/build" \
    -DCMAKE_CXX_COMPILER="$compiler" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_CXX_FLAGS=-include\ bits/stdc++.h
cmake --build "$build_parent/build" --parallel "${SLURM_CPUS_PER_TASK:-2}"
binary=$(find "$build_parent/build" -type f -name chips -perm -u+x -print -quit)
[[ -n "$binary" ]]

mkdir -p "$install_root/bin" "$install_root/provenance"
install -m 0755 "$binary" "$install_root/bin/chips"
{
    printf 'chips_version\tv2.4\n'
    printf 'chips_commit\t%s\n' "$expected_commit"
    printf 'source_sha256\t%s\n' "$observed_source_sha256"
    printf 'binary_sha256\t%s\n' "$(sha256sum "$install_root/bin/chips" | cut -d' ' -f1)"
    printf 'compiler_path\t%s\n' "$compiler"
    printf 'compiler\t%s\n' "$("$compiler" --version | head -n 1)"
    printf 'cmake\t%s\n' "$(cmake --version | head -n 1)"
    printf 'compatibility_cxx_flags\t%s\n' '-include bits/stdc++.h'
    printf 'slurm_job_id\t%s\n' "$SLURM_JOB_ID"
    printf 'hostname\t%s\n' "$(hostname -f 2>/dev/null || hostname)"
} > "$install_root/provenance/runtime.tsv"
sha256sum "$install_root/bin/chips" "$source_tar" > "$install_root/provenance/checksums.sha256"
"$install_root/bin/chips" > "$install_root/provenance/chips.help.txt" 2>&1 || true
