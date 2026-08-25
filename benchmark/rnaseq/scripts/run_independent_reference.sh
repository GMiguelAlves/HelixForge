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
cpus=${SLURM_CPUS_PER_TASK:-2}
test -n "${SLURM_JOB_ID:-}"
test ! -e "$output"
mkdir -p "$output/index" "$output/quant" "$output/logs" "$output/provenance"

"$salmon" index -t "$transcriptome" -i "$output/index" -p "$cpus" -k 31 \
    > "$output/logs/salmon_index.log" 2>&1

while IFS=$'\t' read -r sample_id condition replicate; do
    [[ "$sample_id" == "sample_id" ]] && continue
    r1="$reads_dir/${sample_id}_R1_trimmed.fastq.gz"
    r2="$reads_dir/${sample_id}_R2_trimmed.fastq.gz"
    test -s "$r1"
    test -s "$r2"
    mkdir -p "$output/quant/$sample_id"
    "$salmon" quant -i "$output/index" -l A -1 "$r1" -2 "$r2" \
        --validateMappings -p "$cpus" -o "$output/quant/$sample_id" \
        > "$output/logs/salmon_${sample_id}.log" 2>&1
done < "$samples"

"$rscript" "$analysis_script" --quant-dir "$output/quant" --tx2gene "$tx2gene" \
    --samples "$samples" --output-dir "$output/analysis" \
    > "$output/logs/tximport_deseq2.log" 2>&1

"$salmon" --version > "$output/provenance/versions.txt"
"$rscript" -e 'cat("R ",getRversion(),"\ntximport ",as.character(packageVersion("tximport")),"\nDESeq2 ",as.character(packageVersion("DESeq2")),"\n",sep="")' \
    >> "$output/provenance/versions.txt"
find "$output" -type f -print0 | sort -z | xargs -0 sha256sum > "$output/provenance/checksums.tsv"
printf '{"status":"complete","slurm_job_id":"%s","node":"%s","cpus":%s}\n' \
    "$SLURM_JOB_ID" "$(hostname)" "$cpus" > "$output/provenance/execution.json"
