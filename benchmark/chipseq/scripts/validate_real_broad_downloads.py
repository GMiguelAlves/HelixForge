#!/usr/bin/env python3
"""Validate exact downloaded artifacts for the K562 H3K27me3 benchmark."""

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


def validate_fastq(path: Path, expected_reads: int, expected_length: int, expected_content_md5: str) -> dict:
    reads = 0
    minimum = None
    maximum = 0
    content = hashlib.md5()
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
            if not header.startswith(b"@") or not plus.startswith(b"+"):
                raise ValueError(f"invalid FASTQ structure at read {reads + 1}: {path}")
            if len(sequence) != len(quality):
                raise ValueError(f"sequence/quality length mismatch at read {reads + 1}: {path}")
            minimum = len(sequence) if minimum is None else min(minimum, len(sequence))
            maximum = max(maximum, len(sequence))
            reads += 1
    if reads != expected_reads:
        raise ValueError(f"read-count mismatch for {path}: {reads} != {expected_reads}")
    if minimum != expected_length or maximum != expected_length:
        raise ValueError(f"read-length mismatch for {path}: {minimum}-{maximum} != {expected_length}")
    if content.hexdigest() != expected_content_md5:
        raise ValueError(f"content MD5 mismatch: {path}")
    return {
        "read_count": reads,
        "minimum_read_length": minimum,
        "maximum_read_length": maximum,
        "content_md5": content.hexdigest(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download-root", required=True, type=Path)
    parser.add_argument("--samples", required=True, type=Path)
    parser.add_argument("--references", required=True, type=Path)
    parser.add_argument("--metadata", required=True, type=Path)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-tsv", required=True, type=Path)
    args = parser.parse_args()

    with args.samples.open(encoding="utf-8", newline="") as handle:
        samples = list(csv.DictReader(handle, delimiter="\t"))
    with args.references.open(encoding="utf-8", newline="") as handle:
        references = [
            row for row in csv.DictReader(handle, delimiter="\t")
            if row["role"] in {"genome_fasta", "annotation_gtf", "blacklist", "broad_reference_peaks", "broad_reference_signal"}
        ]
    metadata = json.loads(args.metadata.read_text(encoding="utf-8"))
    if metadata.get("status") != "METADATA_VALIDATED":
        raise ValueError("official metadata snapshot is not validated")
    observed_metadata = {item["accession"]: item for item in metadata["files"]}

    artifacts = []
    table_rows = []
    for row in samples:
        path = args.download_root / "fastq" / f"{row['file_accession']}.fastq.gz"
        if not path.is_file() or path.stat().st_size != int(row["file_size_bytes"]):
            raise ValueError(f"file size mismatch: {path}")
        md5 = digest(path, "md5")
        if md5 != row["md5"]:
            raise ValueError(f"MD5 mismatch: {path}")
        fastq = validate_fastq(path, int(row["read_count"]), int(row["read_length_bp"]), row["content_md5"])
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
        expected_md5 = row["md5"] if row["md5"] != "NA" else observed_metadata[row["accession_or_release"]]["md5sum"]
        if md5 != expected_md5:
            raise ValueError(f"MD5 mismatch: {path}")
        if path.suffix == ".gz" and subprocess.run(["gzip", "-t", str(path)], check=False).returncode:
            raise ValueError(f"gzip integrity failure: {path}")
        artifacts.append({
            "role": row["role"],
            "provider": row["provider"],
            "accession": row["accession_or_release"],
            "assembly": row["assembly"],
            "path": str(path.resolve()),
            "size_bytes": path.stat().st_size,
            "md5": md5,
            "sha256": digest(path, "sha256"),
            "source": row["download_url"],
        })

    result = {
        "schema_version": "1.0",
        "type": "real_broad_download_manifest",
        "status": "DOWNLOAD_CHECKSUM_VALIDATED",
        "validated_utc": datetime.now(timezone.utc).isoformat(),
        "artifacts": artifacts,
        "total_download_bytes": sum(item["size_bytes"] for item in artifacts),
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    with args.output_tsv.open("w", encoding="utf-8", newline="") as handle:
        fields = [
            "sample_id", "experiment_accession", "file_accession", "role", "layout", "read_count",
            "minimum_read_length", "maximum_read_length", "size_bytes", "md5", "content_md5", "sha256", "source", "path",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(table_rows)


if __name__ == "__main__":
    main()
