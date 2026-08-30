#!/usr/bin/env bash

set -euo pipefail

repo_root=${1:?repository root is required}
dataset_root=${2:?dataset root is required}
output_root=${3:?output root is required}
frozen_runtime=${4:?frozen ChIP runtime is required}
deeptools_runtime=${5:?deepTools runtime is required}
helixforge_rep1_bam=${6:?HelixForge replicate 1 BAM is required}
helixforge_rep2_bam=${7:?HelixForge replicate 2 BAM is required}
independent_rep1_bam=${8:?independent replicate 1 BAM is required}
independent_rep2_bam=${9:?independent replicate 2 BAM is required}

[[ -n "${SLURM_JOB_ID:-}" ]] || {
    echo "Broad coverage evaluation must run under Slurm." >&2
    exit 2
}
[[ ! -e "$output_root" ]] || {
    echo "Refusing to overwrite broad coverage output: $output_root" >&2
    exit 2
}
for bam in "$helixforge_rep1_bam" "$helixforge_rep2_bam" "$independent_rep1_bam" "$independent_rep2_bam"; do
    [[ -s "$bam" ]]
done

export PATH="$deeptools_runtime/bin:$frozen_runtime/bin:/usr/bin:/bin"
threads=${SLURM_CPUS_PER_TASK:-4}
mkdir -p "$output_root/bigwig" "$output_root/provenance"

python "$repo_root/benchmark/chipseq/scripts/prepare_broad_coverage_bins.py" \
    --config "$repo_root/benchmark/chipseq/configs/broad_design.json" \
    --repeats "$dataset_root/reference/synthetic_chip_v1.repeats.bed" \
    --truth-strength "$dataset_root/truth/broad_domain_strength.tsv" \
    --output-bed "$output_root/eligible_500bp_bins.bed" \
    --expected-tsv "$output_root/expected_signal.tsv"

labels=(helixforge_rep1 helixforge_rep2 independent_rep1 independent_rep2)
bams=("$helixforge_rep1_bam" "$helixforge_rep2_bam" "$independent_rep1_bam" "$independent_rep2_bam")
bigwigs=()
for index in "${!labels[@]}"; do
    label=${labels[$index]}
    bigwig="$output_root/bigwig/${label}.cpm.bw"
    bamCoverage -b "${bams[$index]}" -o "$bigwig" \
        -p "$threads" --binSize 500 --normalizeUsing CPM \
        > "$output_root/provenance/${label}.bamCoverage.stdout.log" \
        2> "$output_root/provenance/${label}.bamCoverage.stderr.log"
    bigwigs+=("$bigwig")
done

multiBigwigSummary BED-file \
    --bwfiles "${bigwigs[@]}" \
    --BED "$output_root/eligible_500bp_bins.bed" \
    --numberOfProcessors "$threads" \
    --outFileName "$output_root/coverage.npz" \
    --outRawCounts "$output_root/coverage_raw.tsv" \
    > "$output_root/provenance/multiBigwigSummary.stdout.log" \
    2> "$output_root/provenance/multiBigwigSummary.stderr.log"

python "$repo_root/benchmark/chipseq/scripts/evaluate_broad_coverage.py" \
    --expected "$output_root/expected_signal.tsv" \
    --observed "$output_root/coverage_raw.tsv" \
    --label helixforge_rep1 --label helixforge_rep2 \
    --label independent_rep1 --label independent_rep2 \
    --output-json "$output_root/coverage_correlations.json" \
    --output-tsv "$output_root/coverage_correlations.tsv"

{
    printf 'tool\tversion\n'
    printf 'bamCoverage\t%s\n' "$(bamCoverage --version 2>&1 | head -n 1)"
    printf 'multiBigwigSummary\t%s\n' "$(multiBigwigSummary --version 2>&1 | head -n 1)"
    printf 'python\t%s\n' "$(python --version 2>&1)"
} > "$output_root/provenance/versions.tsv"
sha256sum "$output_root/eligible_500bp_bins.bed" "$output_root/expected_signal.tsv" \
    "$output_root/coverage_raw.tsv" "$output_root/coverage_correlations.json" \
    "$output_root/coverage_correlations.tsv" > "$output_root/provenance/checksums.sha256"
