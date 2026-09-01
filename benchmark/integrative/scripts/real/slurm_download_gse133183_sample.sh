#!/usr/bin/env bash
set -euo pipefail

scratch_root=${HF_SCRATCH_ROOT:?HF_SCRATCH_ROOT is required}
manifest=${HF_DOWNLOAD_MANIFEST:?HF_DOWNLOAD_MANIFEST is required}
task=${SLURM_ARRAY_TASK_ID:?SLURM_ARRAY_TASK_ID is required}
case "$scratch_root" in
    /scratch/Schisto-epigenetics/gustavo/helixforge-integrative-real-*) ;;
    *) echo "unsafe scratch root: $scratch_root" >&2; exit 2 ;;
esac
[[ "$task" =~ ^([1-9]|1[0-6])$ ]]
test -s "$manifest"

gsm=$(awk -F '\t' 'NR > 1 {print $1}' "$manifest" | sort -u | sed -n "${task}p")
test -n "$gsm"
fastq_dir="$scratch_root/fastq"
manifest_dir="$scratch_root/download_manifests"
mkdir -p "$fastq_dir" "$manifest_dir"
started=$(date -u +%Y-%m-%dT%H:%M:%SZ)
records=0
files_part="$manifest_dir/${gsm}.files.tsv.part"
printf 'geo_sample\trun_accession\tmate\tpath\tmd5\tbytes\n' > "$files_part"

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
    curl --fail --location --retry 12 --retry-delay 20 --retry-all-errors \
        --continue-at - --output "$partial" "$url"
    [[ "$(stat -c '%s' "$partial")" == "$expected_bytes" ]]
    printf '%s  %s\n' "$expected_md5" "$partial" | md5sum -c -
    gzip -t "$partial"
    mv -- "$partial" "$destination"
}

while IFS=$'\t' read -r row_gsm run assay mark condition replicate mate url md5 bytes; do
    [[ "$row_gsm" == "$gsm" ]] || continue
    [[ "$mate" =~ ^[12]$ ]]
    destination="$fastq_dir/${gsm}_${run}_R${mate}.fastq.gz"
    download_one "$url" "$md5" "$bytes" "$destination"
    printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$gsm" "$run" "$mate" "$destination" "$md5" "$bytes" \
        >> "$files_part"
    records=$((records + 1))
done < <(tail -n +2 "$manifest")
[[ "$records" == 2 ]]
mv -- "$files_part" "$manifest_dir/${gsm}.files.tsv"
ended=$(date -u +%Y-%m-%dT%H:%M:%SZ)
printf 'geo_sample\tstarted_utc\tended_utc\tslurm_job_id\tarray_task_id\tstatus\n' \
    > "$manifest_dir/${gsm}.execution.tsv"
printf '%s\t%s\t%s\t%s\t%s\tCOMPLETE\n' "$gsm" "$started" "$ended" "$SLURM_JOB_ID" "$task" \
    >> "$manifest_dir/${gsm}.execution.tsv"
