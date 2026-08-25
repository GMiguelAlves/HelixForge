#!/usr/bin/env python3
"""Convert paired Polyester FASTA files to deterministic gzip FASTQ."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path


def records(path: Path):
    with path.open(encoding="ascii") as handle:
        header = None
        sequence: list[str] = []
        for raw in handle:
            line = raw.strip()
            if not line:
                continue
            if line.startswith(">"):
                if header is not None:
                    yield header, "".join(sequence)
                header, sequence = line[1:], []
            elif header is None:
                raise ValueError(f"sequence before header in {path}")
            else:
                sequence.append(line)
        if header is not None:
            yield header, "".join(sequence)


def normalized_id(header: str) -> str:
    value = header.split()[0]
    return value.removesuffix("/1").removesuffix("/2")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--r1-fasta", required=True, type=Path)
    parser.add_argument("--r2-fasta", required=True, type=Path)
    parser.add_argument("--r1-fastq", required=True, type=Path)
    parser.add_argument("--r2-fastq", required=True, type=Path)
    parser.add_argument("--quality", default="I")
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args()
    if len(args.quality) != 1:
        raise ValueError("quality must be one ASCII character")
    args.r1_fastq.parent.mkdir(parents=True, exist_ok=True)
    args.r2_fastq.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    iterator1, iterator2 = iter(records(args.r1_fasta)), iter(records(args.r2_fasta))
    with args.r1_fastq.open("wb") as raw1, args.r2_fastq.open("wb") as raw2:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw1, mtime=0) as gz1, \
             gzip.GzipFile(filename="", mode="wb", fileobj=raw2, mtime=0) as gz2:
            while True:
                left = next(iterator1, None)
                right = next(iterator2, None)
                if left is None and right is None:
                    break
                if left is None or right is None:
                    raise ValueError("mate FASTA record counts differ")
                left_id, right_id = normalized_id(left[0]), normalized_id(right[0])
                if left_id != right_id:
                    raise ValueError(f"mate ID mismatch at pair {count + 1}: {left_id} != {right_id}")
                count += 1
                identifier = f"{left_id}:pair{count}"
                gz1.write(f"@{identifier}/1\n{left[1]}\n+\n{args.quality * len(left[1])}\n".encode("ascii"))
                gz2.write(f"@{identifier}/2\n{right[1]}\n+\n{args.quality * len(right[1])}\n".encode("ascii"))

    document = {
        "schema_version": "1.0",
        "pairs": count,
        "quality_character": args.quality,
        "inputs": {str(args.r1_fasta): sha256(args.r1_fasta), str(args.r2_fasta): sha256(args.r2_fasta)},
        "outputs": {str(args.r1_fastq): sha256(args.r1_fastq), str(args.r2_fastq): sha256(args.r2_fastq)},
    }
    args.manifest.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "valid", "pairs": count}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

