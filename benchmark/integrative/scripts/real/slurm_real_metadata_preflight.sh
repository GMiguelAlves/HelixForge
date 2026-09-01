#!/usr/bin/env bash
set -euo pipefail

repo_root=${HF_REPO_ROOT:?HF_REPO_ROOT is required}
scratch_root=${HF_SCRATCH_ROOT:?HF_SCRATCH_ROOT is required}
python_bin=${HF_PYTHON_BIN:-python3}
state="$scratch_root/benchmark_state.json"
sources="$scratch_root/metadata.sources"
output="$scratch_root/metadata"
selection="$repo_root/benchmark/integrative/datasets/real_sample_selection.tsv"
updater="$repo_root/benchmark/integrative/scripts/real/update_real_benchmark_state.py"
validator="$repo_root/benchmark/integrative/scripts/real/validate_gse133183_metadata.py"

test -n "${SLURM_JOB_ID:-}"
case "$scratch_root" in
    /scratch/Schisto-epigenetics/gustavo/helixforge-integrative-real-*) ;;
    *) echo "unsafe scratch root: $scratch_root" >&2; exit 2 ;;
esac
test -d "$scratch_root"
test ! -e "$output"
mkdir -p "$sources/ena"

export HF_STATE_TIME_UTC
HF_STATE_TIME_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)
"$python_bin" "$updater" --state "$state" \
    --phase METADATA_PREFLIGHT_RUNNING --status RUNNING \
    --job-id "$SLURM_JOB_ID" --workdir "$scratch_root"

mark_failed() {
    local code=$?
    HF_STATE_TIME_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ) \
        "$python_bin" "$updater" --state "$state" \
        --phase METADATA_PREFLIGHT_FAILED --status FAILED \
        --job-id "$SLURM_JOB_ID" --workdir "$scratch_root" || true
    exit "$code"
}
trap mark_failed ERR

curl --fail --location --retry 5 --retry-all-errors \
    --output "$sources/GSE133183_family.soft.gz" \
    'https://ftp.ncbi.nlm.nih.gov/geo/series/GSE133nnn/GSE133183/soft/GSE133183_family.soft.gz'
gzip -t "$sources/GSE133183_family.soft.gz"
curl --fail --location --retry 5 --retry-all-errors \
    --output "$sources/ncbi_runinfo.csv" \
    'https://trace.ncbi.nlm.nih.gov/Traces/sra-db-be/runinfo?acc=SRP211748'

while IFS=$'\t' read -r gsm _; do
    [[ "$gsm" == geo_sample ]] && continue
    curl --fail --location --retry 5 --retry-all-errors --get \
        --data-urlencode 'result=read_run' \
        --data-urlencode "query=sample_alias=\"${gsm}\"" \
        --data-urlencode 'fields=run_accession,sample_accession,secondary_sample_accession,sample_alias,experiment_accession,experiment_title,library_strategy,library_source,library_selection,library_layout,instrument_platform,instrument_model,read_count,base_count,first_public,last_updated,fastq_ftp,fastq_md5,fastq_bytes' \
        --data-urlencode 'format=tsv' \
        --output "$sources/ena/${gsm}.tsv" \
        'https://www.ebi.ac.uk/ena/portal/api/search'
done < "$selection"

"$python_bin" "$validator" \
    --selection "$selection" \
    --ena-dir "$sources/ena" \
    --runinfo "$sources/ncbi_runinfo.csv" \
    --geo-soft "$sources/GSE133183_family.soft.gz" \
    --reference-sources "$repo_root/benchmark/integrative/datasets/reference_sources.tsv" \
    --scratch-root "$scratch_root" \
    --output-dir "$output"
mv "$sources" "$output/sources"

HF_STATE_TIME_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ) \
    "$python_bin" "$updater" --state "$state" \
    --phase METADATA_PREFLIGHT_COMPLETE --status COMPLETE \
    --job-id "$SLURM_JOB_ID" --workdir "$scratch_root"
trap - ERR
