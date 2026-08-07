#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path


def read_table(path: Path) -> tuple[list[str], list[list[str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle, delimiter="\t"))
    return rows[0], rows[1:]


def compare_matrix(left: Path, right: Path, tolerance: float = 1e-8) -> tuple[int, float]:
    left_header, left_rows = read_table(left)
    right_header, right_rows = read_table(right)
    if left_header != right_header:
        raise AssertionError(f"header mismatch: {left.name}")
    if [row[0] for row in left_rows] != [row[0] for row in right_rows]:
        raise AssertionError(f"gene order mismatch: {left.name}")
    max_delta = 0.0
    for left_row, right_row in zip(left_rows, right_rows, strict=True):
        if len(left_row) != len(right_row):
            raise AssertionError(f"column count mismatch: {left.name}")
        for observed, expected in zip(left_row[1:], right_row[1:], strict=True):
            delta = abs(float(observed) - float(expected))
            scale = max(1.0, abs(float(expected)))
            max_delta = max(max_delta, delta)
            if delta > tolerance * scale:
                raise AssertionError(f"numeric mismatch in {left.name}: {observed} != {expected}")
    return len(left_rows), max_delta


def compare_samples(left: Path, right: Path) -> int:
    left_header, left_rows = read_table(left)
    right_header, right_rows = read_table(right)
    if left_header != right_header:
        raise AssertionError("sample table header mismatch")
    quant_index = left_header.index("quant_file") if "quant_file" in left_header else -1
    for left_row, right_row in zip(left_rows, right_rows, strict=True):
        for index, (observed, expected) in enumerate(zip(left_row, right_row, strict=True)):
            if index == quant_index:
                if Path(observed).name != Path(expected).name:
                    raise AssertionError("sample quantification filename mismatch")
            elif observed.lower() != expected.lower():
                raise AssertionError(f"sample table mismatch: {observed} != {expected}")
    return len(left_rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("legacy", type=Path)
    parser.add_argument("native", type=Path)
    parser.add_argument("--provider", required=True, choices=("salmon", "star"))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    abundance_name = "tpm_matrix.tsv" if args.provider == "salmon" else "star_cpm_matrix.tsv"
    checks: list[tuple[str, str, str]] = []
    genes, delta = compare_matrix(args.legacy / "counts_matrix.tsv", args.native / "counts_matrix.tsv")
    checks.append(("counts", "pass", f"genes={genes};max_delta={delta}"))
    genes, delta = compare_matrix(args.legacy / abundance_name, args.native / abundance_name)
    checks.append(("abundance", "pass", f"genes={genes};max_delta={delta}"))
    samples = compare_samples(args.legacy / "quant_samples.tsv", args.native / "quant_samples.tsv")
    checks.append(("sample_table", "pass", f"samples={samples}"))

    manifest = json.loads((args.native / "import_manifest.json").read_text(encoding="utf-8"))
    if manifest.get("provider") != args.provider or manifest.get("sample_count") != samples:
        raise AssertionError("native import manifest identity mismatch")
    checks.append(("manifest", "pass", "provider_and_sample_count"))

    if args.provider == "salmon":
        left_header, left_rows = read_table(args.legacy / "tx2gene.tsv")
        right_header, right_rows = read_table(args.native / "tx2gene.tsv")
        if left_header != right_header or left_rows != right_rows:
            raise AssertionError("tx2gene mismatch")
        if not (args.native / "length_matrix.tsv").is_file():
            raise AssertionError("native length matrix missing")
        if not (args.native / "summarized_experiment.rds").is_file():
            raise AssertionError("native SummarizedExperiment missing")
        checks.append(("tx2gene", "pass", f"rows={len(left_rows)}"))
        checks.append(("additive_outputs", "pass", "lengths_and_summarized_experiment"))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(["artifact", "status", "details"])
        writer.writerows(checks)


if __name__ == "__main__":
    main()
