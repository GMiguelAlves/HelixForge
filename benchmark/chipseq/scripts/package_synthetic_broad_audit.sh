#!/usr/bin/env bash

set -euo pipefail

if [[ -z "${SLURM_JOB_ID:-}" ]]; then
    echo "This audit package must be created inside a Slurm allocation." >&2
    exit 2
fi

if [[ $# -ne 3 ]]; then
    echo "usage: $0 SCRATCH_ROOT HOME_AUDIT_DIR README_TEMPLATE" >&2
    exit 2
fi

scratch_root="$(realpath "$1")"
home_audit_dir="$(realpath -m "$2")"
readme_template="$(realpath "$3")"
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

if [[ "$scratch_root" != "/scratch/Schisto-epigenetics/gustavo/helixforge-chipseq-broad-benchmark-20260828" ]]; then
    echo "refusing unexpected scratch root: $scratch_root" >&2
    exit 2
fi
case "$home_audit_dir" in
    /home/ra236875@bio.ib.unicamp.br/helixforge-chipseq-benchmark-*) ;;
    *) echo "refusing unexpected audit destination: $home_audit_dir" >&2; exit 2 ;;
esac

mkdir -p "$home_audit_dir"
stage="$(mktemp -d "$scratch_root/audit-stage.XXXXXX")"
trap 'rm -rf -- "$stage"' EXIT

copy_path() {
    local source="$1"
    local destination="$2"
    if [[ -e "$source" ]]; then
        mkdir -p "$(dirname "$stage/$destination")"
        cp -a "$source" "$stage/$destination"
    fi
}

copy_compact_tree() {
    local source="$1"
    local destination="$2"
    local path relative
    [[ -d "$source" ]] || return 0
    while IFS= read -r -d '' path; do
        case "${path##*/}" in
            eligible_500bp_bins.bed|coverage_raw.tsv|expected_signal.tsv|*.npz)
                continue
                ;;
            *.json|*.yml|*.yaml|*.tsv|*.psv|*.txt|*.log|*.done|*.sha256|*.broadPeak|*.xls|*.bed|*.png|*.pdf|*.html|*.config|*.nf|*.py|*.sh)
                relative="${path#"$source"/}"
                mkdir -p "$stage/$destination/$(dirname "$relative")"
                cp -a "$path" "$stage/$destination/$relative"
                ;;
        esac
    done < <(find "$source" -type f -print0)
}

cp "$readme_template" "$stage/README.md"
copy_path "$repo_root/benchmark/chipseq/configs" "protocol/configs"
copy_path "$repo_root/benchmark/chipseq/protocol" "protocol/documents"
copy_compact_tree "$repo_root/benchmark/chipseq/scripts" "protocol/scripts"
copy_compact_tree "$scratch_root/preflight" "preflight"
copy_compact_tree "$scratch_root/dataset/provenance" "dataset/provenance"
copy_path "$scratch_root/dataset/truth" "dataset/truth"
copy_path "$scratch_root/runtime/chipseq-frozen-provenance" "runtime/chipseq-frozen-provenance"
copy_path "$scratch_root/runtime/chips-hybrid-gcc12/provenance" "runtime/chips-hybrid-gcc12/provenance"
copy_compact_tree "$scratch_root/runtime/chips-hybrid-smoke" "runtime/chips-hybrid-smoke"
copy_path "$scratch_root/helixforge/logs" "helixforge/logs"
copy_path "$scratch_root/helixforge/trace.tsv" "helixforge/trace.tsv"
copy_path "$scratch_root/helixforge/report.html" "helixforge/report.html"
copy_path "$scratch_root/helixforge/timeline.html" "helixforge/timeline.html"
copy_path "$scratch_root/helixforge/dag.html" "helixforge/dag.html"
copy_compact_tree "$scratch_root/helixforge/results/pipeline_info" "helixforge/results/pipeline_info"
copy_compact_tree "$scratch_root/helixforge/results/030-qc-fastq" "helixforge/results/030-qc-fastq"
copy_compact_tree "$scratch_root/helixforge/results/080-peak-calling" "helixforge/results/080-peak-calling"
copy_compact_tree "$scratch_root/helixforge/results/chipseq/consensus" "helixforge/results/chipseq/consensus"
copy_path "$scratch_root/independent/commands" "independent/commands"
copy_path "$scratch_root/independent/provenance" "independent/provenance"
copy_path "$scratch_root/independent/qc" "independent/qc"
copy_compact_tree "$scratch_root/independent/peaks" "independent/peaks"
copy_compact_tree "$scratch_root/independent/consensus" "independent/consensus"
copy_path "$scratch_root/evaluation/technical" "evaluation/technical"
copy_path "$scratch_root/evaluation/scientific" "evaluation/scientific"
copy_compact_tree "$scratch_root/evaluation/coverage" "evaluation/coverage"
copy_path "$scratch_root/evaluation/provenance" "evaluation/provenance"
copy_path "$scratch_root/figures" "figures"
copy_path "$scratch_root/performance" "performance"
copy_compact_tree "$scratch_root/evaluation-attempt1-coordinate-order" "diagnostics/evaluation-attempt1-coordinate-order"
copy_compact_tree "$scratch_root/performance-attempt1-user-id" "diagnostics/performance-attempt1-user-id"
copy_compact_tree "$scratch_root/performance-attempt2-user-id" "diagnostics/performance-attempt2-user-id"
copy_compact_tree "$scratch_root/performance-attempt3-slurmdbd" "diagnostics/performance-attempt3-slurmdbd"
copy_path "$scratch_root/slurm_logs" "slurm_logs"

(
    cd "$stage"
    find . -type f ! -name checksums.sha256 -print0 \
        | sort -z \
        | xargs -0 sha256sum > checksums.sha256
)

archive="$home_audit_dir/helixforge-chipseq-synthetic-broad-audit-20260829.zip"
rm -f -- "$archive" "$archive.sha256"
(
    cd "$stage"
    if command -v zip >/dev/null 2>&1; then
        zip -q -r "$archive" .
    else
        python3 -m zipfile -c "$archive" .
    fi
)
sha256sum "$archive" > "$archive.sha256"
printf '%s\n' "$archive"
