#!/usr/bin/env bash

set -euo pipefail

chips_binary=${1:?ChIPs binary is required}
reference_fasta=${2:?indexed reference FASTA is required}
output_dir=${3:?smoke-test output directory is required}

[[ -n "${SLURM_JOB_ID:-}" ]] || {
    echo "The ChIPs WCE smoke test must run in a Slurm allocation." >&2
    exit 2
}
[[ -x "$chips_binary" ]]
[[ -s "$reference_fasta" ]]
[[ -s "${reference_fasta}.fai" ]]
[[ ! -e "$output_dir" ]] || {
    echo "Refusing to overwrite WCE smoke-test output: $output_dir" >&2
    exit 2
}

mkdir -p "$output_dir"
"$chips_binary" simreads \
    -f "$reference_fasta" \
    -o "$output_dir/input_smoke" \
    --numcopies 2 \
    --numreads 10000 \
    --readlen 75 \
    --paired \
    --gamma-frag 15,12 \
    --pcr_rate 0.85 \
    --seed 20260913 \
    --thread 1 \
    -t wce \
    > "$output_dir/chips.stdout.log" \
    2> "$output_dir/chips.stderr.log"

for mate in 1 2; do
    fastq="$output_dir/input_smoke_${mate}.fastq"
    [[ -s "$fastq" ]]
    [[ "$(wc -l < "$fastq")" -eq 40000 ]]
done

sha256sum "$output_dir"/input_smoke_*.fastq > "$output_dir/checksums.sha256"
{
    printf 'status\tPASS\n'
    printf 'slurm_job_id\t%s\n' "$SLURM_JOB_ID"
    printf 'hostname\t%s\n' "$(hostname -f 2>/dev/null || hostname)"
    printf 'chips_binary_sha256\t%s\n' "$(sha256sum "$chips_binary" | cut -d' ' -f1)"
    printf 'reference_sha256\t%s\n' "$(sha256sum "$reference_fasta" | cut -d' ' -f1)"
    printf 'read_pairs\t10000\n'
    printf 'seed\t20260913\n'
} > "$output_dir/smoke_test.tsv"

