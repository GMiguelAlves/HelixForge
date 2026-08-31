#!/usr/bin/env python3
"""Build an independent two-replicate support consensus for broad intervals."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def read_intervals(path: Path) -> dict[str, list[tuple[int, int]]]:
    intervals: dict[str, list[tuple[int, int]]] = defaultdict(list)
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip() or line.startswith("#"):
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 3:
                raise ValueError(f"{path}:{line_number}: expected at least three columns")
            start, end = int(fields[1]), int(fields[2])
            if start < 0 or end <= start:
                raise ValueError(f"{path}:{line_number}: invalid interval")
            intervals[fields[0]].append((start, end))
    return dict(intervals)


def merge_intervals(rows: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[list[int]] = []
    for start, end in sorted(rows):
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return [(start, end) for start, end in merged]


def intersect_atomic(left: dict[str, list[tuple[int, int]]], right: dict[str, list[tuple[int, int]]]) -> list[tuple[str, int, int]]:
    result = []
    for chrom in sorted(set(left) & set(right)):
        left_rows, right_rows = merge_intervals(left[chrom]), merge_intervals(right[chrom])
        i = j = 0
        while i < len(left_rows) and j < len(right_rows):
            start = max(left_rows[i][0], right_rows[j][0])
            end = min(left_rows[i][1], right_rows[j][1])
            if start < end:
                result.append((chrom, start, end))
            if left_rows[i][1] <= right_rows[j][1]:
                i += 1
            else:
                j += 1
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--peak", action="append", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--statistics", type=Path)
    args = parser.parse_args()
    if len(args.peak) != 2:
        raise ValueError("the frozen broad benchmark requires exactly two replicates")
    consensus = intersect_atomic(read_intervals(args.peak[0]), read_intervals(args.peak[1]))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        for index, (chrom, start, end) in enumerate(consensus, 1):
            handle.write(f"{chrom}\t{start}\t{end}\tINDEPENDENT_SUPPORT2_{index:06d}\n")
    if args.statistics:
        statistics = {
            "schema_version": "1.0",
            "strategy": "replicate_support",
            "replicate_count": 2,
            "support_threshold": 2,
            "consolidated_regions": len(consensus),
            "covered_bases": sum(end - start for _chrom, start, end in consensus),
            "status": "complete" if consensus else "complete_empty",
        }
        args.statistics.write_text(json.dumps(statistics, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
