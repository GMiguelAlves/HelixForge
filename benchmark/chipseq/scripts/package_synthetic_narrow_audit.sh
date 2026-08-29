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

case "$scratch_root" in
    /scratch/Schisto-epigenetics/gustavo/helixforge-chipseq-benchmark-*) ;;
    *) echo "refusing unexpected scratch root: $scratch_root" >&2; exit 2 ;;
esac
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
            eligible_units.bed|units_in_peaks.bed)
                continue
                ;;
            *.json|*.yml|*.yaml|*.tsv|*.txt|*.log|*.done|*.sha256|*.narrowPeak|*.xls|*.bed|*.png|*.html)
                relative="${path#"$source"/}"
                mkdir -p "$stage/$destination/$(dirname "$relative")"
                cp -a "$path" "$stage/$destination/$relative"
                ;;
        esac
    done < <(find "$source" -type f -print0)
}

cp "$readme_template" "$stage/README.md"
copy_path "$scratch_root/preflight.json" "preflight/preflight.json"
copy_path "$scratch_root/dataset/provenance" "dataset/provenance"
copy_path "$scratch_root/dataset/truth" "dataset/truth"
copy_path "$scratch_root/runtime/chips-v2.4-gcc12-default/install/provenance" "runtime/chips/provenance"
copy_path "$scratch_root/helixforge/logs" "helixforge/logs"
copy_path "$scratch_root/helixforge/trace.tsv" "helixforge/trace.tsv"
copy_path "$scratch_root/helixforge/report.html" "helixforge/report.html"
copy_path "$scratch_root/helixforge/timeline.html" "helixforge/timeline.html"
copy_path "$scratch_root/helixforge/dag.html" "helixforge/dag.html"
copy_compact_tree "$scratch_root/helixforge/results/pipeline_info/native_chipseq" "helixforge/results/pipeline_info/native_chipseq"
copy_compact_tree "$scratch_root/helixforge/results/pipeline_info/native_qc" "helixforge/results/pipeline_info/native_qc"
copy_compact_tree "$scratch_root/helixforge/results/080-peak-calling" "helixforge/results/080-peak-calling"
copy_compact_tree "$scratch_root/helixforge/results/chipseq/consensus" "helixforge/results/chipseq/consensus"
copy_path "$scratch_root/independent/commands" "independent/commands"
copy_path "$scratch_root/independent/provenance" "independent/provenance"
copy_path "$scratch_root/independent/qc" "independent/qc"
copy_compact_tree "$scratch_root/independent/peaks" "independent/peaks"
copy_compact_tree "$scratch_root/independent/idr" "independent/idr"
copy_path "$scratch_root/evaluation/selected-v3" "evaluation/technical"
copy_path "$scratch_root/evaluation/metrics" "evaluation/metrics"
copy_path "$scratch_root/evaluation/figures-v2" "evaluation/figures"
copy_path "$scratch_root/evaluation/performance" "evaluation/performance"
copy_path "$scratch_root/evaluation/sacct.tsv" "evaluation/sacct.tsv"
copy_path "$scratch_root/logs" "slurm_logs"

(
    cd "$stage"
    find . -type f ! -name checksums.sha256 -print0 \
        | sort -z \
        | xargs -0 sha256sum > checksums.sha256
)

archive="$home_audit_dir/helixforge-chipseq-synthetic-narrow-audit-20260828.zip"
rm -f -- "$archive"
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
