#!/usr/bin/env python3
"""Validate one downloaded GSE52778 paired FASTQ and emit its checkpoint."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path


def digest(path: Path, algorithm: str) -> str:
    value = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def record(handle, path: Path) -> tuple[bytes, int] | None:
    header = handle.readline()
    if not header:
        return None
    sequence = handle.readline().rstrip(b"\r\n")
    plus = handle.readline()
    quality = handle.readline().rstrip(b"\r\n")
    if not sequence or not plus or not quality:
        raise ValueError(f"truncated FASTQ record in {path}")
    if not header.startswith(b"@") or not plus.startswith(b"+"):
        raise ValueError(f"invalid FASTQ structure in {path}")
    if len(sequence) != len(quality):
        raise ValueError(f"sequence/quality length mismatch in {path}")
    identifier = header[1:].split()[0]
    for suffix in (b"/1", b"/2"):
        if identifier.endswith(suffix):
            identifier = identifier[:-2]
    return identifier, len(sequence)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", required=True)
    parser.add_argument("--run", required=True)
    parser.add_argument("--donor", required=True)
    parser.add_argument("--condition", required=True)
    parser.add_argument("--r1", required=True, type=Path)
    parser.add_argument("--r2", required=True, type=Path)
    parser.add_argument("--r1-md5", required=True)
    parser.add_argument("--r2-md5", required=True)
    parser.add_argument("--r1-bytes", required=True, type=int)
    parser.add_argument("--r2-bytes", required=True, type=int)
    parser.add_argument("--expected-pairs", required=True, type=int)
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args()
    if not os.environ.get("SLURM_JOB_ID"):
        raise SystemExit("FASTQ validation must execute inside a Slurm job")
    for path, expected_bytes in ((args.r1, args.r1_bytes), (args.r2, args.r2_bytes)):
        if not path.is_file() or path.stat().st_size != expected_bytes:
            raise ValueError(f"missing or size-invalid FASTQ: {path}")
    observed_md5 = {"R1": digest(args.r1, "md5"), "R2": digest(args.r2, "md5")}
    if observed_md5 != {"R1": args.r1_md5, "R2": args.r2_md5}:
        raise ValueError("downloaded FASTQ MD5 differs from ENA")

    count = 0
    minimum = [10 ** 9, 10 ** 9]
    maximum = [0, 0]
    with gzip.open(args.r1, "rb") as left, gzip.open(args.r2, "rb") as right:
        while True:
            first, second = record(left, args.r1), record(right, args.r2)
            if first is None or second is None:
                if first is not None or second is not None:
                    raise ValueError("mates contain different record counts")
                break
            if first[0] != second[0]:
                raise ValueError(f"mate ID mismatch near record {count + 1}")
            count += 1
            minimum[0], minimum[1] = min(minimum[0], first[1]), min(minimum[1], second[1])
            maximum[0], maximum[1] = max(maximum[0], first[1]), max(maximum[1], second[1])
    if count != args.expected_pairs:
        raise ValueError(f"paired records differ from official metadata: {count} != {args.expected_pairs}")

    report = {
        "schema_version": "1.0",
        "status": "DOWNLOAD_READY",
        "slurm_job_id": os.environ["SLURM_JOB_ID"],
        "sample_id": args.sample,
        "run_accession": args.run,
        "donor": args.donor,
        "condition": args.condition,
        "paired_records": count,
        "read_length": {"R1": [minimum[0], maximum[0]], "R2": [minimum[1], maximum[1]]},
        "files": {
            "R1": {"path": str(args.r1), "bytes": args.r1.stat().st_size,
                   "md5": observed_md5["R1"], "sha256": digest(args.r1, "sha256")},
            "R2": {"path": str(args.r2), "bytes": args.r2.stat().st_size,
                   "md5": observed_md5["R2"], "sha256": digest(args.r2, "sha256")},
        },
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.manifest.with_suffix(args.manifest.suffix + f".{os.environ['SLURM_JOB_ID']}.tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(args.manifest)
    print(json.dumps({"status": "DOWNLOAD_READY", "sample": args.sample, "pairs": count}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
