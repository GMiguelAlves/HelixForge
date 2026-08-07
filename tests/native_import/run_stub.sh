#!/usr/bin/env bash

set -euo pipefail

project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
nextflow_bin=${NEXTFLOW_BIN:-nextflow}
fixture_root="${project_root}/tests/fixtures/native_import"
case_root="${project_root}/results/test/native-import-stub"

for provider in salmon star; do
    "$nextflow_bin" run "${project_root}/tests/native_import/main.nf" \
        -c "${project_root}/tests/native_import/nextflow.config" \
        -profile local -stub-run -ansi-log false \
        --provider "$provider" \
        --fixture_root "$fixture_root" \
        --target_root "${case_root}/${provider}/outputs" \
        --outdir "${case_root}/${provider}/nextflow"
done

test -s "${case_root}/salmon/outputs/counts_matrix.tsv"
test -s "${case_root}/salmon/outputs/length_matrix.tsv"
test -s "${case_root}/salmon/outputs/summarized_experiment.rds"
test -s "${case_root}/star/outputs/counts_matrix.tsv"
test -s "${case_root}/star/outputs/star_cpm_matrix.tsv"
test ! -e "${case_root}/star/outputs/length_matrix.tsv"
echo '[OK] Import API stub contracts validated for Salmon and STAR.'
