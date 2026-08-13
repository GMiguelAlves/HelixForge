#!/usr/bin/env bash

set -euo pipefail

validation_root=${1:?validation root is required}
conda_bin=${2:?conda executable is required}
mode=${3:-plan}
prefix="$validation_root/runtime/idr"
plan="$validation_root/idr-conda-plan.json"
summary="$validation_root/idr-conda-plan-summary.json"

case "$validation_root" in
    /scratch/Schisto-epigenetics/gustavo/helixforge-idr-validation-*) ;;
    *) echo "Refusing unexpected validation root: $validation_root" >&2; exit 2 ;;
esac
test -n "${SLURM_JOB_ID:-}"
test -x "$conda_bin"
mkdir -p "$validation_root/runtime"

if [[ "$mode" == "plan" ]]; then
    "$conda_bin" create --dry-run --json --yes --prefix "$prefix" \
        --channel conda-forge --channel bioconda \
        python=3.9 'idr=2.0.4.2=py39h031d066_12' > "$plan"
    python3 - "$plan" "$summary" <<'PY'
import json
import pathlib
import sys

source, target = map(pathlib.Path, sys.argv[1:])
document = json.loads(source.read_text(encoding="utf-8"))
fetch = document.get("actions", {}).get("FETCH", [])
link = document.get("actions", {}).get("LINK", [])
summary = {
    "schema_version": "1.0",
    "packages_to_fetch": len(fetch),
    "packages_to_link": len(link),
    "download_bytes": sum(int(item.get("size", 0)) for item in fetch),
    "requested": ["python=3.9", "idr=2.0.4.2=py39h031d066_12"],
    "status": "planned",
}
target.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(summary, sort_keys=True))
PY
elif [[ "$mode" == "install" ]]; then
    test -s "$summary"
    "$conda_bin" create --yes --prefix "$prefix" \
        --channel conda-forge --channel bioconda \
        python=3.9 'idr=2.0.4.2=py39h031d066_12'
    "$prefix/bin/idr" --version
else
    echo "mode must be plan or install" >&2
    exit 2
fi
