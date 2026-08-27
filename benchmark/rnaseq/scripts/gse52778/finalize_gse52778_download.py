#!/usr/bin/env python3
"""Aggregate eight validated GSE52778 run checkpoints into DOWNLOAD_READY."""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metadata", required=True, type=Path)
    parser.add_argument("--download-root", required=True, type=Path)
    args = parser.parse_args()
    if not os.environ.get("SLURM_JOB_ID"):
        raise SystemExit("download finalization must execute inside a Slurm job")
    with args.metadata.open(encoding="utf-8", newline="") as handle:
        metadata = list(csv.DictReader(handle, delimiter="\t"))
    if len(metadata) != 8:
        raise ValueError("expected eight metadata rows")
    rows = []
    checksum_lines = []
    total_pairs = total_bytes = 0
    for expected in metadata:
        sample = f"{expected['donor']}_{expected['condition']}"
        manifest_path = args.download_root / f"manifests/{sample}.json"
        report = json.loads(manifest_path.read_text(encoding="utf-8"))
        if report.get("status") != "DOWNLOAD_READY" or report.get("run_accession") != expected["run_accession"]:
            raise ValueError(f"invalid run checkpoint: {sample}")
        if int(report["paired_records"]) != int(expected["paired_spots"]):
            raise ValueError(f"paired-record mismatch: {sample}")
        files = report["files"]
        for mate in ("R1", "R2"):
            path = Path(files[mate]["path"])
            if not path.is_file() or path.stat().st_size != int(files[mate]["bytes"]):
                raise ValueError(f"missing finalized file: {path}")
            checksum_lines.append(f"{files[mate]['sha256']}  {path}\n")
            total_bytes += int(files[mate]["bytes"])
        total_pairs += int(report["paired_records"])
        rows.append({
            "sample_id": sample,
            "run_accession": report["run_accession"],
            "donor": report["donor"],
            "condition": report["condition"],
            "paired_records": report["paired_records"],
            "r1": files["R1"]["path"],
            "r2": files["R2"]["path"],
            "r1_bytes": files["R1"]["bytes"],
            "r2_bytes": files["R2"]["bytes"],
            "r1_md5": files["R1"]["md5"],
            "r2_md5": files["R2"]["md5"],
            "r1_sha256": files["R1"]["sha256"],
            "r2_sha256": files["R2"]["sha256"],
            "validation_job": report["slurm_job_id"],
        })
    manifest = args.download_root / "download_manifest.tsv"
    checksums = args.download_root / "checksums.sha256"
    checkpoint = args.download_root / "DOWNLOAD_READY.json"
    for path in (manifest, checksums, checkpoint):
        if path.exists():
            raise FileExistsError(path)
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    checksums.write_text("".join(checksum_lines), encoding="utf-8")
    summary = {
        "schema_version": "1.0",
        "status": "DOWNLOAD_READY",
        "slurm_job_id": os.environ["SLURM_JOB_ID"],
        "libraries": len(rows),
        "fastq_files": len(rows) * 2,
        "paired_records": total_pairs,
        "compressed_bytes": total_bytes,
        "metadata": str(args.metadata),
        "manifest": str(manifest),
        "checksums": str(checksums),
    }
    checkpoint.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
