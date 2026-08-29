#!/usr/bin/env python3
"""Evaluate frozen CPM BigWig coverage vectors for the broad benchmark."""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from pathlib import Path


def ranks(values: list[float]) -> list[float]:
    result = [0.0] * len(values)
    order = sorted(range(len(values)), key=lambda index: (values[index], index))
    cursor = 0
    while cursor < len(order):
        end = cursor + 1
        while end < len(order) and values[order[end]] == values[order[cursor]]:
            end += 1
        rank = (cursor + end - 1) / 2 + 1
        for position in order[cursor:end]:
            result[position] = rank
        cursor = end
    return result


def pearson(left: list[float], right: list[float]) -> float | None:
    if len(left) != len(right) or len(left) < 2:
        return None
    left_mean, right_mean = statistics.fmean(left), statistics.fmean(right)
    numerator = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right))
    left_ss = sum((a - left_mean) ** 2 for a in left)
    right_ss = sum((b - right_mean) ** 2 for b in right)
    return numerator / math.sqrt(left_ss * right_ss) if left_ss and right_ss else None


def read_expected(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def read_observed(path: Path) -> tuple[list[str], list[str], list[dict]]:
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        raise ValueError("empty multiBigwigSummary raw-count file")
    header = lines[0].lstrip("#").replace("'", "").split("\t")
    rows = [dict(zip(header, line.split("\t"))) for line in lines[1:]]
    if len(header) < 5:
        raise ValueError("expected coordinates plus at least two BigWig columns")
    return header[:3], header[3:], rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected", required=True, type=Path)
    parser.add_argument("--observed", required=True, type=Path)
    parser.add_argument("--label", action="append", required=True)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-tsv", required=True, type=Path)
    args = parser.parse_args()
    expected = read_expected(args.expected)
    coordinate_columns, columns, observed = read_observed(args.observed)
    if len(columns) != len(args.label):
        raise ValueError("BigWig column count does not match labels")
    if len(expected) != len(observed):
        raise ValueError("expected and observed bin counts differ")
    expected_signal, vectors = [], {label: [] for label in args.label}
    for expected_row, observed_row in zip(expected, observed):
        coordinates = (expected_row["chrom"], expected_row["start"], expected_row["end"])
        if coordinates != tuple(observed_row[column] for column in coordinate_columns):
            raise ValueError("expected and observed bin coordinates differ")
        expected_signal.append(float(expected_row["expected_signal"]))
        for label, column in zip(args.label, columns):
            vectors[label].append(float(observed_row[column]))
    rows = []
    for label, vector in vectors.items():
        rows.append({"left": "expected_signal", "right": label, "bins": len(vector), "pearson": pearson(expected_signal, vector), "spearman": pearson(ranks(expected_signal), ranks(vector))})
    for left_index, left in enumerate(args.label):
        for right in args.label[left_index + 1 :]:
            rows.append({"left": left, "right": right, "bins": len(vectors[left]), "pearson": pearson(vectors[left], vectors[right]), "spearman": pearson(ranks(vectors[left]), ranks(vectors[right]))})
    with args.output_tsv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    document = {
        "schema_version": "1.0",
        "type": "synthetic_broad_coverage_correlation",
        "bin_size_bp": 500,
        "normalization": "CPM BigWig",
        "eligible_bins": "full 500 bp bins with no repeat overlap",
        "bin_count": len(expected),
        "correlations": rows,
        "status": "complete",
    }
    args.output_json.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
