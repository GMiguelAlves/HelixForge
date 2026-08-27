#!/usr/bin/env python3
"""Verify the Stage 9B.1 audit ZIP and its external SHA-256 sidecar."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import zipfile


REQUIRED_MEMBERS = {
    "helixforge-rnaseq-stage9b1-audit/README_PT.md",
    "helixforge-rnaseq-stage9b1-audit/MANIFEST_SHA256.txt",
    "helixforge-rnaseq-stage9b1-audit/benchmark/reports/stage_9b1_results.md",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("checksum", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--required-member", action="append")
    args = parser.parse_args()
    if not os.environ.get("SLURM_JOB_ID"):
        raise SystemExit("archive verification must execute inside a Slurm job")

    expected = args.checksum.read_text(encoding="utf-8").split()[0]
    observed = sha256(args.archive)
    with zipfile.ZipFile(args.archive) as archive:
        corrupt_member = archive.testzip()
        names = set(archive.namelist())
    required_members = set(args.required_member or REQUIRED_MEMBERS)
    missing = sorted(required_members - names)
    report = {
        "status": "pass" if expected == observed and not corrupt_member and not missing else "fail",
        "slurm_job_id": os.environ["SLURM_JOB_ID"],
        "archive": str(args.archive),
        "sha256_expected": expected,
        "sha256_observed": observed,
        "member_count": len(names),
        "corrupt_member": corrupt_member,
        "missing_required_members": missing,
    }
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "members": len(names)}))
    if report["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
