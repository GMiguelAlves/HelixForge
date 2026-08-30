#!/usr/bin/env python3
"""Validate exact downloaded files for the K562 CTCF benchmark."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def digest(path: Path, algorithm: str) -> str:
    value = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def validate_fastq(path: Path, expected_reads: int, expected_length: int) -> dict:
    reads = 0
    minimum = None
    maximum = 0
    with gzip.open(path, "rt", encoding="ascii", newline="") as handle:
        while True:
            header = handle.readline()
            if not header:
                break
            sequence = handle.readline().rstrip("\r\n")
            plus = handle.readline()
            quality = handle.readline().rstrip("\r\n")
            if not header.startswith("@") or not plus.startswith("+"):
                raise ValueError(f"invalid FASTQ structure at read {reads + 1}: {path}")
            if len(sequence) != len(quality):
                raise ValueError(f"sequence/quality length mismatch at read {reads + 1}: {path}")
            length = len(sequence)
            minimum = length if minimum is None else min(minimum, length)
            maximum = max(maximum, length)
            reads += 1
    if reads != expected_reads:
        raise ValueError(f"read-count mismatch for {path}: {reads} != {expected_reads}")
    if minimum != expected_length or maximum != expected_length:
        raise ValueError(f"read-length mismatch for {path}: {minimum}-{maximum} != {expected_length}")
    return {"read_count": reads, "minimum_read_length": minimum, "maximum_read_length": maximum}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download-root", required=True, type=Path)
    parser.add_argument("--samples", required=True, type=Path)
    parser.add_argument("--references", required=True, type=Path)
    parser.add_argument("--motif", required=True, type=Path)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-tsv", required=True, type=Path)
    args = parser.parse_args()

    if not subprocess.run(["gzip", "--version"], capture_output=True, check=False).returncode == 0:
        raise RuntimeError("gzip is unavailable")
    with args.samples.open(encoding="utf-8", newline="") as handle:
        samples = list(csv.DictReader(handle, delimiter="\t"))
    with args.references.open(encoding="utf-8", newline="") as handle:
        references = [
            row for row in csv.DictReader(handle, delimiter="\t")
            if row["role"] in {"genome_fasta", "annotation_gtf", "blacklist", "narrow_reference_peaks", "narrow_reference_signal"}
        ]

    artifacts = []
    table_rows = []
    for row in samples:
        path = args.download_root / "fastq" / f"{row['file_accession']}.fastq.gz"
        if not path.is_file() or path.stat().st_size != int(row["file_size_bytes"]):
            raise ValueError(f"file size mismatch: {path}")
        md5 = digest(path, "md5")
        if md5 != row["md5"]:
            raise ValueError(f"MD5 mismatch: {path}")
        fastq = validate_fastq(path, int(row["read_count"]), int(row["read_length_bp"]))
        artifact = {
            "role": row["assay_role"].lower(),
            "sample_id": row["sample_id"],
            "experiment_accession": row["experiment_accession"],
            "file_accession": row["file_accession"],
            "path": str(path.resolve()),
            "size_bytes": path.stat().st_size,
            "md5": md5,
            "sha256": digest(path, "sha256"),
            "layout": row["layout"],
            **fastq,
            "source": row["download_url"],
        }
        artifacts.append(artifact)
        table_rows.append(artifact)

    for row in references:
        subdir = "reference" if row["role"] in {"genome_fasta", "annotation_gtf", "blacklist"} else "external"
        path = args.download_root / subdir / row["filename"]
        if not path.is_file():
            raise FileNotFoundError(path)
        md5 = digest(path, "md5")
        if md5 != row["md5"]:
            raise ValueError(f"MD5 mismatch: {path}")
        if path.suffix == ".gz" and subprocess.run(["gzip", "-t", str(path)], check=False).returncode:
            raise ValueError(f"gzip integrity failure: {path}")
        artifacts.append(
            {
                "role": row["role"],
                "provider": row["provider"],
                "accession": row["accession_or_release"],
                "assembly": row["assembly"],
                "path": str(path.resolve()),
                "size_bytes": path.stat().st_size,
                "md5": md5,
                "sha256": digest(path, "sha256"),
                "source": row["download_url"],
            }
        )

    motif = args.motif
    if not motif.is_file() or not motif.read_text(encoding="utf-8").startswith(">MA0139.1\tCTCF"):
        raise ValueError("JASPAR MA0139.1 motif validation failed")
    artifacts.append(
        {
            "role": "motif",
            "provider": "JASPAR CORE",
            "accession": "MA0139.1",
            "path": str(motif.resolve()),
            "size_bytes": motif.stat().st_size,
            "sha256": digest(motif, "sha256"),
            "source": "https://jaspar.elixir.no/api/v1/matrix/MA0139.1.jaspar",
        }
    )

    result = {
        "schema_version": "1.0",
        "type": "real_narrow_download_manifest",
        "status": "DOWNLOAD_CHECKSUM_VALIDATED",
        "validated_utc": datetime.now(timezone.utc).isoformat(),
        "artifacts": artifacts,
        "total_download_bytes": sum(item["size_bytes"] for item in artifacts),
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    with args.output_tsv.open("w", encoding="utf-8", newline="") as handle:
        fields = [
            "sample_id", "experiment_accession", "file_accession", "role", "layout",
            "read_count", "minimum_read_length", "maximum_read_length", "size_bytes",
            "md5", "sha256", "source", "path",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(table_rows)


if __name__ == "__main__":
    main()
