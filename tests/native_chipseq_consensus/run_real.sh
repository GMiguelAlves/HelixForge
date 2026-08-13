#!/usr/bin/env bash

set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
nextflow_bin=${NEXTFLOW:-nextflow}
image=${IDR_TEST_IMAGE:-quay.io/biocontainers/idr:2.0.4.2--py39h031d066_12@sha256:d6fb2a7eb69bb236278562d08fcd0b62bfbe2e887d330111c6aea1e42cb26caa}
case_root=${IDR_TEST_ROOT:-$(mktemp -d "${TMPDIR:-/tmp}/helixforge-idr.XXXXXX")}

mkdir -p "$case_root/fixture" "$case_root/results" "$case_root/work" "$case_root/nxf-home"
python3 "$root/tests/native_chipseq_consensus/generate_fixture.py" --outdir "$case_root/fixture"

NXF_HOME="$case_root/nxf-home" "$nextflow_bin" run "$root/tests/native_chipseq_consensus/main.nf" \
    -c "$root/tests/native_chipseq_consensus/nextflow.config" \
    -c "$root/tests/native_chipseq_consensus/real.config" \
    -ansi-log false \
    -work-dir "$case_root/work" \
    --fixture_dir "$case_root/fixture" \
    --outdir "$case_root/results" \
    --chipseq_run_mode idr \
    --idr_container "$image"

docker image inspect --format='{{index .RepoDigests 0}}' "$image" \
    > "$case_root/image_digest.txt"
python3 "$root/tests/native_chipseq_consensus/validate_real.py" --root "$case_root"
printf '[OK] IDR real certification: %s\n' "$case_root/certification.json"
