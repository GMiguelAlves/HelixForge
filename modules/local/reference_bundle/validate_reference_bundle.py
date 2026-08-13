#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
from pathlib import Path


def open_text(path: Path):
    return gzip.open(path, "rt", encoding="utf-8") if path.suffix.lower() == ".gz" else path.open(encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_fasta(path: Path, label: str) -> int:
    identifiers: set[str] = set()
    sequence_lines = 0
    current = None
    with open_text(path) as handle:
        for number, raw in enumerate(handle, start=1):
            line = raw.strip()
            if not line:
                continue
            if line.startswith(">"):
                identifier = line[1:].split(maxsplit=1)[0]
                if not identifier:
                    raise ValueError(f"{label} FASTA has an empty identifier at line {number}")
                if identifier in identifiers:
                    raise ValueError(f"{label} FASTA has duplicate identifier: {identifier}")
                identifiers.add(identifier)
                current = identifier
            else:
                if current is None:
                    raise ValueError(f"{label} FASTA sequence precedes its first header")
                sequence_lines += 1
    if not identifiers or sequence_lines == 0:
        raise ValueError(f"{label} FASTA contains no sequences")
    return len(identifiers)


def validate_annotation(path: Path) -> int:
    features = 0
    with open_text(path) as handle:
        for number, raw in enumerate(handle, start=1):
            line = raw.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            columns = line.split("\t")
            if len(columns) != 9:
                raise ValueError(f"annotation line {number} does not contain 9 columns")
            try:
                start, end = int(columns[3]), int(columns[4])
            except ValueError as error:
                raise ValueError(f"annotation line {number} has invalid coordinates") from error
            if start < 1 or end < start:
                raise ValueError(f"annotation line {number} has invalid interval {start}-{end}")
            features += 1
    if features == 0:
        raise ValueError("annotation contains no features")
    return features


def artifact(path: Path, role: str) -> dict[str, object]:
    return {
        "role": role,
        "name": path.name,
        "size": path.stat().st_size,
        "sha256": sha256(path),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference-id", required=True)
    parser.add_argument("--organism", default="")
    parser.add_argument("--transcriptome", required=True, type=Path)
    parser.add_argument("--annotation", required=True, type=Path)
    parser.add_argument("--genome", type=Path)
    parser.add_argument("--run-mode", default="full")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()

    try:
        required = (("transcriptome", args.transcriptome), ("annotation", args.annotation))
        for label, path in required:
            if not path.is_file() or path.stat().st_size == 0:
                raise ValueError(f"{label} is missing or empty: {path}")
        if args.genome and (not args.genome.is_file() or args.genome.stat().st_size == 0):
            raise ValueError(f"genome is missing or empty: {args.genome}")

        transcripts = validate_fasta(args.transcriptome, "transcriptome")
        sequences = validate_fasta(args.genome, "genome") if args.genome else None
        features = validate_annotation(args.annotation)
        artifacts = [artifact(args.transcriptome, "transcriptome"), artifact(args.annotation, "annotation")]
        if args.genome:
            artifacts.append(artifact(args.genome, "genome"))

        document = {
            "schema_version": "1.0",
            "type": "reference_bundle",
            "id": args.reference_id,
            "organism": args.organism,
            "status": "complete",
            "artifacts": artifacts,
        }
        args.manifest.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report = {
            "schema_version": "1.0", "status": "valid", "reference_id": args.reference_id,
            "transcript_sequences": transcripts, "genome_sequences": sequences,
            "annotation_features": features,
        }
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"validated reference bundle {args.reference_id}: {transcripts} transcripts, {features} features")
        return 0
    except (OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
