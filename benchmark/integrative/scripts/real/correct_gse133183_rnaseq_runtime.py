#!/usr/bin/env python3
"""Correct the Conda activation root without changing native certified runtimes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path


REPLACEMENTS = {
    "export CONDA_BASE=/scratch/Schisto-epigenetics/gustavo/helixforge-rnaseq-benchmark-20260825/envs":
        "export CONDA_BASE=/home/ra236875@bio.ib.unicamp.br/miniconda3",
    "export RNA_TOOLS_ENV='rna-tools-rc'": "export RNA_TOOLS_ENV='rna-tools'",
    "export PYTHON_ENV='python-runtime-rc'": "export PYTHON_ENV='python-list'",
    "export R_ANALYSIS_ENV='r-analysis-rc'": "export R_ANALYSIS_ENV='r-analysis'",
}


def digest(path: Path) -> str:
    value = hashlib.sha256(path.read_bytes()).hexdigest()
    return value


def artifact(path: Path) -> dict[str, object]:
    return {"path": str(path), "sha256": digest(path), "size_bytes": path.stat().st_size}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-root", required=True, type=Path)
    parser.add_argument("--repository-commit", required=True)
    args = parser.parse_args()
    if not os.environ.get("SLURM_JOB_ID"):
        raise SystemExit("runtime correction must execute inside a Slurm job")
    settings = args.case_root / "user_settings.sh"
    backup = args.case_root / "user_settings.pre-runtime-fix.sh"
    correction = args.case_root / "runtime_correction.json"
    manifest_path = args.case_root / "input_manifest.json"
    if backup.exists() or correction.exists():
        raise FileExistsError("runtime correction was already applied")
    original = settings.read_text(encoding="utf-8")
    updated = original
    for before, after in REPLACEMENTS.items():
        if before not in updated:
            raise ValueError(f"expected frozen runtime setting is absent: {before}")
        updated = updated.replace(before, after, 1)
    backup.write_text(original, encoding="utf-8", newline="\n")
    settings.write_text(updated, encoding="utf-8", newline="\n")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.setdefault("artifacts", {})["user_settings"] = artifact(settings)
    manifest["runtime_correction"] = {
        "status": "APPLIED_PRE_ANALYSIS",
        "reason": "Conda activator root was confused with the certified environment directory",
        "native_runtime_policy": "unchanged; certified runtimes remain first in the Nextflow driver PATH",
        "slurm_job_id": os.environ["SLURM_JOB_ID"],
        "repository_commit": args.repository_commit,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    correction.write_text(json.dumps({
        "schema_version": "1.0", "status": "COMPLETE", "scope": "rnaseq_planning_adapters_only",
        "reason": manifest["runtime_correction"]["reason"], "repository_commit": args.repository_commit,
        "slurm_job_id": os.environ["SLURM_JOB_ID"], "before": artifact(backup), "after": artifact(settings),
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
