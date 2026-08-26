#!/usr/bin/env bash
set -euo pipefail

scratch_root=${1:?benchmark scratch root is required}
audit_root=${2:?audit home root is required}
report=${3:?cleanup report path is required}

test -n "${SLURM_JOB_ID:-}"
expected_scratch=/scratch/Schisto-epigenetics/gustavo/helixforge-rnaseq-benchmark-20260825
expected_audit=/home/ra236875@bio.ib.unicamp.br/helixforge-rnaseq-benchmark-audits/20260825-9b1
[[ "$(realpath "$scratch_root")" == "$expected_scratch" ]]
[[ "$(realpath "$audit_root")" == "$expected_audit" ]]
[[ "$(realpath "$(dirname "$report")")" == "$expected_audit" ]]

sha256sum -c "$audit_root/helixforge-rnaseq-stage9b1-audit-20260826.zip.sha256"
sha256sum -c "$audit_root/helixforge-rnaseq-stage9b1-failed-attempts-20260826.zip.sha256"
python3 - "$scratch_root" <<'PY'
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1], "validation")
for name in ("audit-archive-verification.json", "failed-attempts-archive-verification.json"):
    report = json.loads((root / name).read_text())
    if report.get("status") != "pass" or report.get("sha256_expected") != report.get("sha256_observed"):
        raise SystemExit(f"audit verification is not valid: {name}")
PY

targets=(
    "$scratch_root/cases/synthetic-primary"
    "$scratch_root/cases/synthetic-primary-run1"
    "$scratch_root/cases/synthetic-primary-run2"
    "$scratch_root/cases/synthetic-clean-repeat"
    "$scratch_root/cases/synthetic-primary-run3/work"
    "$scratch_root/cases/synthetic-clean-repeat-v2/work"
)

bytes_before=0
for target in "${targets[@]}"; do
    test -d "$target"
    test ! -L "$target"
    resolved=$(realpath "$target")
    [[ "$resolved" == "$expected_scratch"/cases/* ]]
    size=$(du -sb "$resolved" | cut -f1)
    bytes_before=$((bytes_before + size))
done

rm -rf -- "${targets[@]}"

for target in "${targets[@]}"; do
    test ! -e "$target"
done

python3 - "$report" "$SLURM_JOB_ID" "$bytes_before" "${targets[@]}" <<'PY'
import json
import pathlib
import sys

output, job_id, bytes_removed, *targets = sys.argv[1:]
report = {
    "status": "pass",
    "slurm_job_id": job_id,
    "bytes_removed": int(bytes_removed),
    "removed_paths": targets,
    "preserved": [
        "dataset/polyester-ground-truth-v1",
        "dataset/reference",
        "envs",
        "cases/synthetic-primary-run3/results",
        "cases/synthetic-clean-repeat-v2/results",
        "independent",
        "metrics",
        "validation",
        "provenance",
    ],
}
pathlib.Path(output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
print(json.dumps({"status": "pass", "bytes_removed": int(bytes_removed), "paths": len(targets)}))
PY
