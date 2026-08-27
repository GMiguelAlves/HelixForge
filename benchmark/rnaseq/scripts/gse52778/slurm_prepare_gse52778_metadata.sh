#!/usr/bin/env bash
set -euo pipefail

repo_root=${1:?repository root is required}
python_bin=${2:?Python executable is required}
output=${3:?metadata output directory is required}
test -n "${SLURM_JOB_ID:-}"
test ! -e "$output"
mkdir -p "$output.sources/xml"

ena_url='https://www.ebi.ac.uk/ena/portal/api/filereport?accession=SRP033351&result=read_run&fields=run_accession,sample_accession,secondary_sample_accession,sample_alias,experiment_accession,library_layout,nominal_length,instrument_platform,instrument_model,read_count,base_count,sra_ftp,sra_md5,sra_bytes,fastq_ftp,fastq_md5,fastq_bytes&format=tsv'
runinfo_url='https://trace.ncbi.nlm.nih.gov/Traces/sra-db-be/runinfo?acc=SRP033351'
geo_url='https://ftp.ncbi.nlm.nih.gov/geo/series/GSE52nnn/GSE52778/soft/GSE52778_family.soft.gz'

curl --fail --location --retry 5 --retry-all-errors --output "$output.sources/ena_read_run.tsv" "$ena_url"
curl --fail --location --retry 5 --retry-all-errors --output "$output.sources/ncbi_runinfo.csv" "$runinfo_url"
curl --fail --location --retry 5 --retry-all-errors --output "$output.sources/GSE52778_family.soft.gz" "$geo_url"
gzip -t "$output.sources/GSE52778_family.soft.gz"

for run in SRR1039508 SRR1039509 SRR1039512 SRR1039513 SRR1039516 SRR1039517 SRR1039520 SRR1039521; do
    curl --fail --location --retry 5 --retry-all-errors \
        --output "$output.sources/xml/${run}.xml" \
        "https://www.ebi.ac.uk/ena/browser/api/xml/${run}"
done

"$python_bin" "$repo_root/benchmark/rnaseq/scripts/gse52778/validate_gse52778_metadata.py" \
    --registry "$repo_root/benchmark/rnaseq/datasets/airway_samples.tsv" \
    --ena "$output.sources/ena_read_run.tsv" \
    --runinfo "$output.sources/ncbi_runinfo.csv" \
    --geo-soft "$output.sources/GSE52778_family.soft.gz" \
    --xml-dir "$output.sources/xml" \
    --output-dir "$output"

mv "$output.sources" "$output/sources"
