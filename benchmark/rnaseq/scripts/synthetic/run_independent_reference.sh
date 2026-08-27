#!/usr/bin/env bash
set -euo pipefail

salmon=${1:?Salmon executable is required}
rscript=${2:?Rscript executable is required}
analysis_script=${3:?independent R script is required}
transcriptome=${4:?transcriptome is required}
tx2gene=${5:?tx2gene is required}
samples=${6:?sample table is required}
reads_dir=${7:?post-trim reads directory is required}
output=${8:?output directory is required}
existing_index=${9:-}
cpus=${SLURM_CPUS_PER_TASK:-2}
test -n "${SLURM_JOB_ID:-}"
test ! -e "$output"
mkdir -p "$output/quant" "$output/logs" "$output/provenance"

if [[ -n "$existing_index" ]]; then
    test -d "$existing_index"
    index=$existing_index
    index_mode=shared_rc_artifact
    find "$existing_index" -type f -print0 | sort -z | xargs -0 sha256sum \
        > "$output/provenance/index_checksums.tsv"
    printf '%s\n' "$existing_index" > "$output/provenance/index_source.txt"
else
    mkdir -p "$output/index"
    index=$output/index
    index_mode=independently_rebuilt
    "$salmon" index -t "$transcriptome" -i "$index" -p "$cpus" -k 31 \
        > "$output/logs/salmon_index.log" 2>&1
fi

while IFS=$'\t' read -r sample_id condition replicate; do
    [[ "$sample_id" == "sample_id" ]] && continue
    r1="$reads_dir/${sample_id}_R1_trimmed.fastq.gz"
    r2="$reads_dir/${sample_id}_R2_trimmed.fastq.gz"
    test -s "$r1"
    test -s "$r2"
    mkdir -p "$output/quant/$sample_id"
    "$salmon" quant -i "$index" -l A -1 "$r1" -2 "$r2" \
        --validateMappings -p "$cpus" -o "$output/quant/$sample_id" \
        > "$output/logs/salmon_${sample_id}.log" 2>&1
done < "$samples"

"$rscript" "$analysis_script" --quant-dir "$output/quant" --tx2gene "$tx2gene" \
    --samples "$samples" --output-dir "$output/analysis" \
    > "$output/logs/tximport_deseq2.log" 2>&1

"$salmon" --version > "$output/provenance/versions.txt"
"$rscript" -e 'cat("R ",as.character(getRversion()),"\ntximport ",as.character(packageVersion("tximport")),"\nDESeq2 ",as.character(packageVersion("DESeq2")),"\n",sep="")' \
    >> "$output/provenance/versions.txt"
find "$output" -type f ! -path "$output/provenance/checksums.tsv" -print0 \
    | sort -z | xargs -0 sha256sum > "$output/provenance/checksums.tsv"
printf '{"status":"complete","slurm_job_id":"%s","node":"%s","cpus":%s,"index_mode":"%s"}\n' \
    "$SLURM_JOB_ID" "$(hostname)" "$cpus" "$index_mode" > "$output/provenance/execution.json"
