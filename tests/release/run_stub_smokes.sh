#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
nextflow_bin="${NEXTFLOW:-${repo_root}/nextflow}"
if [[ ! -x "${nextflow_bin}" ]]; then
    nextflow_bin="$(command -v "${NEXTFLOW:-nextflow}" || true)"
fi
if [[ -z "${nextflow_bin}" ]]; then
    echo "Nextflow not found; set NEXTFLOW=/absolute/path/to/nextflow" >&2
    exit 2
fi

smoke_root="$(mktemp -d "${TMPDIR:-/tmp}/helixforge-rc-smoke.XXXXXX")"
trap 'rm -rf -- "${smoke_root}"' EXIT

cd "${repo_root}"
python3 tests/integrative_workflow/prepare_fixture.py --output "${smoke_root}/fixture"

"${nextflow_bin}" run . -profile test -stub-run \
    --workflow rnaseq --rnaseq_run_mode full --outdir "${smoke_root}/rnaseq"
test -s "${smoke_root}/rnaseq/rnaseq/rnaseq_run_manifest.json"

"${nextflow_bin}" run . -profile test -stub-run \
    --workflow chipseq --chipseq_run_mode full --outdir "${smoke_root}/chipseq"
test -s "${smoke_root}/chipseq/chipseq/chipseq_run_manifest.json"

"${nextflow_bin}" run . -profile test -stub-run \
    --workflow integrative \
    --rna_manifest "${smoke_root}/fixture/rna/rnaseq_run_manifest.json" \
    --chip_manifest "${smoke_root}/fixture/chip/chipseq_run_manifest.json" \
    --outdir "${smoke_root}/integrative"
test -s "${smoke_root}/integrative/integration/integrative_run_manifest.json"

"${nextflow_bin}" run . -profile test -stub-run \
    --workflow all --outdir "${smoke_root}/all"
test -s "${smoke_root}/all/rnaseq/rnaseq_run_manifest.json"
test -s "${smoke_root}/all/chipseq/chipseq_run_manifest.json"
test -s "${smoke_root}/all/integration/integrative_run_manifest.json"

echo "All four public workflow stub smokes passed"
