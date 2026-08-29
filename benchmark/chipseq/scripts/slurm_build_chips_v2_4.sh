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
c_compiler=${CC:-/usr/bin/gcc}
cxx_compiler=${CXX:-/usr/bin/g++}
[[ -x "$c_compiler" && -x "$cxx_compiler" ]] || {
    echo "System C/C++ compilers are not executable: $c_compiler $cxx_compiler" >&2
    exit 2
}
portable_cxx_flags='-march=x86-64 -mtune=generic -include bits/stdc++.h'
portable_c_flags='-march=x86-64 -mtune=generic'
export CC="$c_compiler"
export CXX="$cxx_compiler"

cmake -S "$source_root" -B "$build_parent/build" \
    -DCMAKE_C_COMPILER="$c_compiler" \
    -DCMAKE_CXX_COMPILER="$cxx_compiler" \
    -DCMAKE_C_FLAGS="$portable_c_flags" \
    -DCMAKE_CXX_FLAGS="$portable_cxx_flags"
cmake --build "$build_parent/build" --parallel "${SLURM_CPUS_PER_TASK:-2}"
binary=$(find "$build_parent/build" -type f -name chips -perm -u+x -print -quit)
[[ -n "$binary" ]]

mkdir -p "$install_root/bin" "$install_root/provenance"
install -m 0755 "$binary" "$install_root/bin/chips"
readelf -n "$install_root/bin/chips" > "$install_root/provenance/elf-notes.txt"
if grep -Eq 'x86-64-v[34]' "$install_root/provenance/elf-notes.txt"; then
    echo "ChIPs binary requires a non-portable x86-64 ISA level" >&2
    exit 2
fi

set +e
"$install_root/bin/chips" > "$install_root/provenance/chips.help.txt" 2>&1
help_status=$?
set -e
if [[ "$help_status" -eq 126 || "$help_status" -eq 127 ]] || \
    grep -q 'CPU ISA level is lower than required' "$install_root/provenance/chips.help.txt"; then
    echo "ChIPs binary failed its runtime portability check" >&2
    exit 2
fi
{
    printf 'chips_version\tv2.4\n'
    printf 'chips_commit\t%s\n' "$expected_commit"
    printf 'source_sha256\t%s\n' "$observed_source_sha256"
    printf 'binary_sha256\t%s\n' "$(sha256sum "$install_root/bin/chips" | cut -d' ' -f1)"
    printf 'c_compiler_path\t%s\n' "$c_compiler"
    printf 'c_compiler\t%s\n' "$("$c_compiler" --version | head -n 1)"
    printf 'cxx_compiler_path\t%s\n' "$cxx_compiler"
    printf 'cxx_compiler\t%s\n' "$("$cxx_compiler" --version | head -n 1)"
    printf 'cmake\t%s\n' "$(cmake --version | head -n 1)"
    printf 'cmake_build_type\t%s\n' 'default (upstream README command)'
    printf 'compatibility_cxx_flags\t%s\n' "$portable_cxx_flags"
    printf 'compatibility_c_flags\t%s\n' "$portable_c_flags"
    printf 'runtime_help_exit_status\t%s\n' "$help_status"
    printf 'slurm_job_id\t%s\n' "$SLURM_JOB_ID"
    printf 'hostname\t%s\n' "$(hostname -f 2>/dev/null || hostname)"
} > "$install_root/provenance/runtime.tsv"
sha256sum "$install_root/bin/chips" "$source_tar" > "$install_root/provenance/checksums.sha256"
