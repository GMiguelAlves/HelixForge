#!/usr/bin/env bash

set -euo pipefail

repo_root=${1:?repository root is required}
benchmark_root=${2:?benchmark root is required}
runtime_prefix=${3:?frozen ChIP runtime prefix is required}

[[ -n "${SLURM_JOB_ID:-}" ]] || {
    echo "Downloads and validation must run in a Slurm allocation." >&2
    exit 2
}

benchmark_root=$(realpath -m "$benchmark_root")
expected_root=/scratch/Schisto-epigenetics/gustavo/helixforge-chipseq-real-narrow-benchmark-20260830
[[ "$benchmark_root" == "$expected_root" ]] || {
    echo "Refusing unexpected benchmark root: $benchmark_root" >&2
    exit 2
}

download_root="$benchmark_root/downloads"
mkdir -p "$download_root"/{fastq,reference,external,motif,provenance}

download() {
    local url=$1
    local destination=$2
    local temporary="${destination}.part"
    curl --location --fail --show-error --silent \
        --retry 5 --retry-delay 10 --continue-at - \
        --output "$temporary" "$url"
    mv -- "$temporary" "$destination"
}

while IFS=$'\t' read -r sample_id condition replicate role experiment accession layout read_length read_count total_bases size md5 content_md5 url; do
    [[ "$sample_id" == "sample_id" ]] && continue
    destination="$download_root/fastq/${accession}.fastq.gz"
    if [[ ! -s "$destination" ]] || [[ "$(stat -c %s "$destination")" != "$size" ]]; then
        download "$url" "$destination"
    fi
done < "$repo_root/benchmark/chipseq/datasets/real_narrow_samples.tsv"

while IFS=$'\t' read -r role provider accession filename assembly md5 url; do
    [[ "$role" == "role" ]] && continue
    case "$role" in
        genome_fasta|annotation_gtf|blacklist)
            destination="$download_root/reference/$filename"
            ;;
        narrow_reference_peaks|narrow_reference_signal)
            destination="$download_root/external/$filename"
            ;;
        *) continue ;;
    esac
    if [[ ! -s "$destination" ]]; then
        download "$url" "$destination"
    fi
done < "$repo_root/benchmark/chipseq/datasets/reference_sources.tsv"

motif="$download_root/motif/MA0139.1.jaspar"
if [[ ! -s "$motif" ]]; then
    download "https://jaspar.elixir.no/api/v1/matrix/MA0139.1.jaspar" "$motif"
fi

"$runtime_prefix/bin/python" \
    "$repo_root/benchmark/chipseq/scripts/validate_real_narrow_downloads.py" \
    --download-root "$download_root" \
    --samples "$repo_root/benchmark/chipseq/datasets/real_narrow_samples.tsv" \
    --references "$repo_root/benchmark/chipseq/datasets/reference_sources.tsv" \
    --motif "$motif" \
    --output-json "$download_root/provenance/download_manifest.json" \
    --output-tsv "$download_root/provenance/dataset_metadata.tsv"

printf 'DOWNLOAD_READY\nDOWNLOAD_CHECKSUM_VALIDATED\n' > "$download_root/provenance/download.status"
