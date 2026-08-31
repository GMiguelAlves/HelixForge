#!/usr/bin/env bash
set -euo pipefail

readonly ROOT="/scratch/Schisto-epigenetics/gustavo/helixforge-chipseq-real-broad-benchmark-20260830"
readonly AUDIT_DIR="/home/ra236875@bio.ib.unicamp.br/helixforge-audit/real-broad"
readonly ARCHIVE="$AUDIT_DIR/HelixForge_real_broad_K562_H3K27me3_20260831.tar.gz"
readonly CHECKSUM="$ARCHIVE.sha256"
readonly RECEIPT="$AUDIT_DIR/cleanup_receipt_20260831.txt"

[[ -n "${SLURM_JOB_ID:-}" ]] || { echo "Cleanup must run under Slurm." >&2; exit 2; }
[[ -d "$ROOT" ]]
[[ "$(realpath -- "$ROOT")" == "$ROOT" ]]
[[ "$ROOT" == /scratch/Schisto-epigenetics/gustavo/helixforge-chipseq-real-broad-benchmark-20260830 ]]
[[ -s "$ARCHIVE" && -s "$CHECKSUM" ]]

sha256sum -c "$CHECKSUM"
listing="$(mktemp "${TMPDIR:-/tmp}/real-broad-audit-list.XXXXXX")"
trap 'rm -f -- "$listing"' EXIT
tar -tzf "$ARCHIVE" > "$listing"
grep -Fxq './README_PT.md' "$listing"
grep -Fq './evidence/evaluation/benchmark_summary.json' "$listing"
grep -Fq './repository/benchmark/chipseq/reports/real_broad_benchmark.md' "$listing"

bytes_before="$(du -sb -- "$ROOT" | cut -f1)"
cat > "$RECEIPT" <<EOF
HELIXFORGE_REAL_BROAD_CLEANUP
timestamp_before=$(date --iso-8601=seconds)
slurm_job_id=$SLURM_JOB_ID
validated_archive=$ARCHIVE
archive_sha256=$(cut -d' ' -f1 "$CHECKSUM")
removed_root=$ROOT
bytes_before=$bytes_before
archive_integrity=PASS
required_readme=PASS
required_evidence=PASS
EOF

rm -rf -- "$ROOT"
[[ ! -e "$ROOT" ]]
{
    printf 'cleanup_status=COMPLETED\n'
    printf 'timestamp_after=%s\n' "$(date --iso-8601=seconds)"
} >> "$RECEIPT"
cat "$RECEIPT"
