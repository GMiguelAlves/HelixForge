#!/usr/bin/env bash
set -euo pipefail

repo=${1:?repository root is required}
snapshot_dir=${2:?snapshot directory is required}
expected=/home/ra236875@bio.ib.unicamp.br/helixforge-audit/real-broad/repository_snapshot

[[ -z "${SLURM_JOB_ID:-}" ]] || { echo "Repository snapshot belongs on the head node, not a compute node." >&2; exit 2; }
[[ "$(realpath -m "$snapshot_dir")" == "$expected" ]] || { echo "Unexpected snapshot directory." >&2; exit 2; }
[[ -d "$repo/.git" ]]

stage="$(mktemp -d "${snapshot_dir}.stage.XXXXXX")"
trap 'rm -rf -- "$stage"' EXIT
git -C "$repo" rev-parse HEAD > "$stage/repository_commit.txt"
git -C "$repo" status --porcelain > "$stage/repository_status.txt"
git -C "$repo" archive --format=tar HEAD \
    benchmark/chipseq/configs/real_broad_execution.json \
    benchmark/chipseq/datasets/real_broad_samples.tsv \
    benchmark/chipseq/datasets/real_broad_biological_expectations.tsv \
    benchmark/chipseq/protocol \
    benchmark/chipseq/reports/real_broad_benchmark.md \
    benchmark/chipseq/results/real_broad \
    benchmark/chipseq/scripts \
    tests/benchmark_chipseq/test_real_broad_benchmark.py \
    > "$stage/repository_snapshot.tar"
(
    cd "$stage"
    sha256sum repository_snapshot.tar > repository_snapshot.tar.sha256
)
rm -rf -- "$snapshot_dir"
mv -- "$stage" "$snapshot_dir"
trap - EXIT
printf 'SNAPSHOT=%s\n' "$snapshot_dir/repository_snapshot.tar"
cat "$snapshot_dir/repository_commit.txt"
cat "$snapshot_dir/repository_snapshot.tar.sha256"
