#!/usr/bin/env python3
"""Audit exact FASTQ checksums, counts, and observed read-length distributions."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def file_md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def audit_fastq(path: Path) -> dict:
    content = hashlib.md5()
    lengths: Counter[int] = Counter()
    reads = 0
    with gzip.open(path, "rb") as handle:
        while True:
            record = [handle.readline() for _ in range(4)]
            if not record[0]:
                break
            if any(not line for line in record[1:]):
                raise ValueError(f"truncated FASTQ record {reads + 1}: {path}")
            for line in record:
                content.update(line)
            header, sequence, plus, quality = (line.rstrip(b"\r\n") for line in record)
            if not header.startswith(b"@") or not plus.startswith(b"+") or len(sequence) != len(quality):
                raise ValueError(f"invalid FASTQ record {reads + 1}: {path}")
            lengths[len(sequence)] += 1
            reads += 1
    return {
        "read_count": reads,
        "content_md5": content.hexdigest(),
        "minimum_read_length": min(lengths),
        "maximum_read_length": max(lengths),
        "length_histogram": {str(length): count for length, count in sorted(lengths.items())},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", required=True, type=Path)
    parser.add_argument("--download-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    with args.samples.open(encoding="utf-8", newline="") as handle:
        samples = list(csv.DictReader(handle, delimiter="\t"))
    results = []
    for row in samples:
        path = args.download_root / "fastq" / f"{row['file_accession']}.fastq.gz"
        observed = audit_fastq(path)
        compressed_md5 = file_md5(path)
        checks = {
            "file_size": path.stat().st_size == int(row["file_size_bytes"]),
            "compressed_md5": compressed_md5 == row["md5"],
            "content_md5": observed["content_md5"] == row["content_md5"],
            "read_count": observed["read_count"] == int(row["read_count"]),
            "metadata_length_uniform": observed["minimum_read_length"] == int(row["read_length_bp"])
            and observed["maximum_read_length"] == int(row["read_length_bp"]),
        }
        if not all(value for name, value in checks.items() if name != "metadata_length_uniform"):
            raise ValueError(f"identity or structure mismatch for {row['file_accession']}: {checks}")
        results.append({
            "file_accession": row["file_accession"],
            "path": str(path.resolve()),
            "declared_read_length": int(row["read_length_bp"]),
            "compressed_md5": compressed_md5,
            "checks": checks,
            **observed,
        })

    result = {
        "schema_version": "1.0",
        "type": "real_broad_fastq_length_audit",
        "status": "IDENTITY_VALIDATED_LENGTH_METADATA_AUDITED",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "files": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
