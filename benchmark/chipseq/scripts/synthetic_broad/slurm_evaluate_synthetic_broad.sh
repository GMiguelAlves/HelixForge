#!/usr/bin/env bash

set -euo pipefail

repo_root=${1:?repository root is required}
benchmark_root=${2:?benchmark root is required}
frozen_runtime=${3:?frozen ChIP runtime is required}
deeptools_runtime=${4:?deepTools runtime is required}

[[ -n "${SLURM_JOB_ID:-}" ]] || {
    echo "Synthetic broad evaluation must run under Slurm." >&2
    exit 2
}
export PATH="$frozen_runtime/bin:/usr/bin:/bin"

dataset_root="$benchmark_root/dataset"
helixforge_run="$benchmark_root/helixforge"
independent_run="$benchmark_root/independent"
evaluation_root="$benchmark_root/evaluation"
[[ ! -e "$evaluation_root" ]] || {
    echo "Refusing to overwrite broad evaluation: $evaluation_root" >&2
    exit 2
}

mkdir -p "$evaluation_root/provenance"
python "$repo_root/benchmark/chipseq/scripts/synthetic_broad/collect_synthetic_broad_outputs.py" \
    --helixforge-run "$helixforge_run" \
    --independent-run "$independent_run" \
    --output-dir "$evaluation_root/technical"

declare -A regions=()
while IFS=$'\t' read -r role path _sha256 _records _size_bytes; do
    [[ "$role" == "role" ]] && continue
    regions["$role"]=$path
done < "$evaluation_root/technical/selected_region_sets.tsv"

declare -A bams=()
while IFS=$'\t' read -r role path _size_bytes; do
    [[ "$role" == "role" ]] && continue
    bams["$role"]=$path
done < "$evaluation_root/technical/selected_bams.tsv"

python "$repo_root/benchmark/chipseq/scripts/synthetic_broad/evaluate_synthetic_broad.py" \
    --config "$repo_root/benchmark/chipseq/configs/broad_design.json" \
    --truth-strength "$dataset_root/truth/broad_domain_strength.tsv" \
    --peak-set "helixforge_rep1=${regions[helixforge_chip_rep1]}" \
    --peak-set "helixforge_rep2=${regions[helixforge_chip_rep2]}" \
    --peak-set "helixforge_consensus=${regions[helixforge_consensus]}" \
    --peak-set "independent_rep1=${regions[independent_chip_rep1]}" \
    --peak-set "independent_rep2=${regions[independent_chip_rep2]}" \
    --peak-set "independent_consensus=${regions[independent_consensus]}" \
    --replicate-pair helixforge_rep1,helixforge_rep2 \
    --replicate-pair independent_rep1,independent_rep2 \
    --comparison-pair helixforge_rep1,independent_rep1 \
    --comparison-pair helixforge_rep2,independent_rep2 \
    --comparison-pair helixforge_consensus,independent_consensus \
    --primary-label helixforge_consensus \
    --output-dir "$evaluation_root/scientific"

bash "$repo_root/benchmark/chipseq/scripts/synthetic_broad/slurm_evaluate_broad_coverage.sh" \
    "$repo_root" "$dataset_root" "$evaluation_root/coverage" \
    "$frozen_runtime" "$deeptools_runtime" \
    "${bams[helixforge_chip_rep1]}" "${bams[helixforge_chip_rep2]}" \
    "${bams[independent_chip_rep1]}" "${bams[independent_chip_rep2]}"

{
    printf 'tool\tversion\n'
    printf 'python\t%s\n' "$(python --version 2>&1)"
    printf 'bamCoverage\t%s\n' "$("$deeptools_runtime/bin/bamCoverage" --version 2>&1 | head -n 1)"
    printf 'multiBigwigSummary\t%s\n' "$("$deeptools_runtime/bin/multiBigwigSummary" --version 2>&1 | head -n 1)"
    printf 'slurm_job_id\t%s\n' "$SLURM_JOB_ID"
    printf 'hostname\t%s\n' "$(hostname -f 2>/dev/null || hostname)"
} > "$evaluation_root/provenance/versions.tsv"

find "$evaluation_root/technical" "$evaluation_root/scientific" "$evaluation_root/coverage" \
    -type f ! -path '*/bigwig/*' ! -name 'coverage.npz' -print0 \
    | sort -z | xargs -0 sha256sum > "$evaluation_root/provenance/checksums.sha256"
