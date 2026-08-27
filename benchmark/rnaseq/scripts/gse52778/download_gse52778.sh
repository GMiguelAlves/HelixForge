#!/usr/bin/env bash
set -euo pipefail

metadata=${1:?validated metadata TSV is required}
python_bin=${2:?Python executable is required}
validator=${3:?FASTQ validator is required}
output_root=${4:?download output root is required}
test -n "${SLURM_JOB_ID:-}"
task=${SLURM_ARRAY_TASK_ID:?array task ID is required}
[[ "$task" =~ ^[1-8]$ ]]
test -s "$metadata"
test -x "$python_bin"
test -f "$validator"

IFS=$'\t' read -r run geo biosample donor condition layout read_length_r1 read_length_r2 \
    ncbi_avg platform model run_spots paired_spots base_count sra_mb r1_bytes r2_bytes \
    paired_bytes extra_files r1_url r2_url r1_md5 r2_md5 \
    < <(awk -F '\t' -v row="$((task + 1))" 'NR == row {print; exit}' "$metadata")
test -n "$run"
test "$layout" = PAIRED

sample="${donor}_${condition}"
fastq_dir="$output_root/fastq"
manifest_dir="$output_root/manifests"
mkdir -p "$fastq_dir" "$manifest_dir"
r1="$fastq_dir/${sample}_R1.fastq.gz"
r2="$fastq_dir/${sample}_R2.fastq.gz"

download_one() {
    local url=$1 expected_md5=$2 expected_bytes=$3 destination=$4
    if [[ -e "$destination" ]]; then
        test -f "$destination"
        [[ "$(stat -c '%s' "$destination")" == "$expected_bytes" ]]
        printf '%s  %s\n' "$expected_md5" "$destination" | md5sum -c -
        gzip -t "$destination"
        return
    fi
    local partial="${destination}.part"
    if [[ -e "$partial" ]]; then
        test -f "$partial"
        [[ "$(stat -c '%s' "$partial")" -le "$expected_bytes" ]]
    fi
    curl --fail --location --retry 10 --retry-delay 15 --retry-all-errors \
        --continue-at - --output "$partial" "$url"
    [[ "$(stat -c '%s' "$partial")" == "$expected_bytes" ]]
    printf '%s  %s\n' "$expected_md5" "$partial" | md5sum -c -
    gzip -t "$partial"
    mv -- "$partial" "$destination"
}

started=$(date -u +%Y-%m-%dT%H:%M:%SZ)
download_one "$r1_url" "$r1_md5" "$r1_bytes" "$r1"
download_one "$r2_url" "$r2_md5" "$r2_bytes" "$r2"
"$python_bin" "$validator" \
    --sample "$sample" --run "$run" --donor "$donor" --condition "$condition" \
    --r1 "$r1" --r2 "$r2" --r1-md5 "$r1_md5" --r2-md5 "$r2_md5" \
    --r1-bytes "$r1_bytes" --r2-bytes "$r2_bytes" --expected-pairs "$paired_spots" \
    --manifest "$manifest_dir/${sample}.json"
chmod 0440 "$r1" "$r2"
ended=$(date -u +%Y-%m-%dT%H:%M:%SZ)
printf '%s\t%s\t%s\t%s\t%s\n' "$sample" "$run" "$started" "$ended" "$SLURM_JOB_ID" \
    > "$manifest_dir/${sample}.execution.tsv"
