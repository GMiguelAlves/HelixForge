#!/usr/bin/env bash
set -euo pipefail

salmon=${1:?Salmon executable is required}
rscript=${2:?Rscript executable is required}
analysis_script=${3:?independent R script is required}
tx2gene=${4:?tx2gene is required}
samples=${5:?sample table is required}
output=${6:?existing independent output directory is required}
quant_job_id=${7:?quantification Slurm job ID is required}
test -n "${SLURM_JOB_ID:-}"
test -d "$output/quant"
test -d "$output/logs"
test -d "$output/provenance"
test ! -e "$output/analysis"

sample_count=0
while IFS=$'\t' read -r sample_id condition batch; do
    [[ "$sample_id" == "sample_id" ]] && continue
    test -s "$output/quant/$sample_id/quant.sf"
    test -s "$output/quant/$sample_id/aux_info/meta_info.json"
    sample_count=$((sample_count + 1))
done < "$samples"
test "$sample_count" -eq 8

"$rscript" "$analysis_script" --quant-dir "$output/quant" --tx2gene "$tx2gene" \
    --samples "$samples" --output-dir "$output/analysis" \
    > "$output/logs/tximport_deseq2.log" 2>&1

"$salmon" --version > "$output/provenance/versions.txt"
"$rscript" -e 'cat("R ",as.character(getRversion()),"\ntximport ",as.character(packageVersion("tximport")),"\nDESeq2 ",as.character(packageVersion("DESeq2")),"\n",sep="")' \
    >> "$output/provenance/versions.txt"
printf '{"status":"complete","type":"independent_analysis_recovery","quantification_job_id":"%s","analysis_job_id":"%s","node":"%s","cpus":%s,"index_mode":"shared_rc_artifact"}\n' \
    "$quant_job_id" "$SLURM_JOB_ID" "$(hostname)" "${SLURM_CPUS_PER_TASK:-1}" \
    > "$output/provenance/execution.json"
find "$output" -type f ! -path "$output/provenance/checksums.tsv" -print0 \
    | sort -z | xargs -0 sha256sum > "$output/provenance/checksums.tsv"
