#!/usr/bin/env python3
"""Fail-closed structural validation and freeze manifest for Polyester v1."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def fastq_id(header: str) -> str:
    value = header.split()[0]
    if not value.startswith("@"):
        raise ValueError(f"invalid FASTQ header: {header[:100]}")
    return value[1:].removesuffix("/1").removesuffix("/2")


def validate_pair(r1: Path, r2: Path, expected: int) -> dict[str, object]:
    count = 0
    with gzip.open(r1, "rt", encoding="ascii", newline="") as left, \
         gzip.open(r2, "rt", encoding="ascii", newline="") as right:
        while True:
            blocks = []
            for handle in (left, right):
                block = [handle.readline() for _ in range(4)]
                blocks.append(block)
            if all(line == "" for block in blocks for line in block):
                break
            if any(line == "" for block in blocks for line in block):
                raise ValueError(f"truncated or unequal FASTQs: {r1}, {r2}")
            for block in blocks:
                if not block[0].startswith("@") or not block[2].startswith("+"):
                    raise ValueError(f"malformed FASTQ record in {r1} or {r2}")
                sequence, quality = block[1].rstrip("\r\n"), block[3].rstrip("\r\n")
                if len(sequence) != len(quality) or not sequence:
                    raise ValueError(f"sequence/quality mismatch in {r1} or {r2}")
            if fastq_id(blocks[0][0].strip()) != fastq_id(blocks[1][0].strip()):
                raise ValueError(f"mate ID mismatch at pair {count + 1}: {r1.name}")
            count += 1
    if count != expected:
        raise ValueError(f"{r1.name}: expected {expected} pairs, observed {count}")
    return {
        "pairs": count,
        "r1": {"path": str(r1), "bytes": r1.stat().st_size, "sha256": sha256(r1)},
        "r2": {"path": str(r2), "bytes": r2.stat().st_size, "sha256": sha256(r2)},
    }


def tracked_files(root: Path) -> dict[str, dict[str, object]]:
    document = {}
    for path in sorted(value for value in root.rglob("*") if value.is_file()):
        document[str(path.relative_to(root))] = {"bytes": path.stat().st_size, "sha256": sha256(path)}
    return document


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--design", required=True, type=Path)
    parser.add_argument("--reference-dir", required=True, type=Path)
    parser.add_argument("--truth-dir", required=True, type=Path)
    parser.add_argument("--fastq-dir", required=True, type=Path)
    parser.add_argument("--output-report", required=True, type=Path)
    parser.add_argument("--output-manifest", required=True, type=Path)
    args = parser.parse_args()

    design = json.loads(args.design.read_text(encoding="utf-8"))
    samples = design["experiment"]["samples"]
    expected_pairs = int(design["library"]["fragments_per_sample"])
    mapping = rows(args.truth_dir / "transcript_to_gene.tsv")
    de = rows(args.truth_dir / "gene_de_truth.tsv")
    sample_rows = rows(args.truth_dir / "sample_table.tsv")
    transcript_truth = rows(args.truth_dir / "transcript_truth.tsv")
    gene_truth = rows(args.truth_dir / "gene_truth.tsv")

    transcript_ids = [row["transcript_id"] for row in mapping]
    gene_ids = sorted({row["gene_id"] for row in mapping})
    if len(transcript_ids) != 2400 or len(set(transcript_ids)) != 2400:
        raise ValueError("truth must contain 2,400 unique transcripts")
    if len(gene_ids) != 1200:
        raise ValueError("truth must contain 1,200 unique genes")
    if [row["sample_id"] for row in sample_rows] != [value["sample_id"] for value in samples]:
        raise ValueError("sample table does not match frozen design order")
    if len(transcript_truth) != 2400 * 6 or len(gene_truth) != 1200 * 6:
        raise ValueError("truth table dimensions are invalid")
    if len(de) != 1200 or len({row["gene_id"] for row in de}) != 1200:
        raise ValueError("DE truth gene universe is invalid")

    states = {"UP": 0, "DOWN": 0, "UNCHANGED": 0}
    for row in de:
        state, effect = row["true_state"], float(row["true_log2fc"])
        states[state] = states.get(state, 0) + 1
        expected_state = "UP" if effect > 0 else "DOWN" if effect < 0 else "UNCHANGED"
        if state != expected_state:
            raise ValueError(f"state/effect mismatch for {row['gene_id']}")
        if (row["is_de"].lower() == "true") != (state != "UNCHANGED"):
            raise ValueError(f"is_de mismatch for {row['gene_id']}")
    if states != {"UP": 120, "DOWN": 120, "UNCHANGED": 960}:
        raise ValueError(f"unexpected DE state counts: {states}")

    fastq_validation = {}
    for sample in samples:
        sample_id = sample["sample_id"]
        r1 = args.fastq_dir / f"{sample_id}_R1.fastq.gz"
        r2 = args.fastq_dir / f"{sample_id}_R2.fastq.gz"
        if not r1.is_file() or not r2.is_file():
            raise FileNotFoundError(f"missing FASTQ pair for {sample_id}")
        fastq_validation[sample_id] = validate_pair(r1, r2, expected_pairs)

    report = {
        "schema_version": "1.0",
        "status": "valid",
        "benchmark_id": "polyester-ground-truth-v1",
        "samples": len(samples),
        "genes": len(gene_ids),
        "transcripts": len(transcript_ids),
        "de_states": states,
        "pairs_per_sample": expected_pairs,
        "fastq": fastq_validation,
    }
    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    args.output_report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    manifest = {
        "schema_version": "1.0",
        "benchmark_id": "polyester-ground-truth-v1",
        "status": "frozen",
        "design": {"path": str(args.design), "sha256": sha256(args.design)},
        "reference": tracked_files(args.reference_dir),
        "truth": tracked_files(args.truth_dir),
        "fastq": fastq_validation,
        "validation_report": {"path": str(args.output_report), "sha256": sha256(args.output_report)},
    }
    args.output_manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "frozen", "benchmark_id": manifest["benchmark_id"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
