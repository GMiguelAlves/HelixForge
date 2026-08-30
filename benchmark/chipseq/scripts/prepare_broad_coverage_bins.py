#!/usr/bin/env python3
"""Create frozen 500 bp repeat-free bins and their expected broad signal."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


BIN_SIZE = 500


def read_repeats(path: Path) -> dict[str, list[tuple[int, int]]]:
    result: dict[str, list[tuple[int, int]]] = defaultdict(list)
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip() and not line.startswith("#"):
                fields = line.rstrip("\n").split("\t")
                result[fields[0]].append((int(fields[1]), int(fields[2])))
    return {chrom: sorted(rows) for chrom, rows in result.items()}


def read_truth(path: Path) -> dict[str, list[dict]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    result: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        result[row["chrom"]].append(
            {"start": int(row["start"]), "end": int(row["end"]), "signal": float(row["signal_strength"])}
        )
    return {chrom: sorted(rows, key=lambda row: (row["start"], row["end"])) for chrom, rows in result.items()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--repeats", required=True, type=Path)
    parser.add_argument("--truth-strength", required=True, type=Path)
    parser.add_argument("--output-bed", required=True, type=Path)
    parser.add_argument("--expected-tsv", required=True, type=Path)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    reference = config["reference"]
    repeats, truth = read_repeats(args.repeats), read_truth(args.truth_strength)
    rows = []
    for chromosome_index in range(1, int(reference["chromosomes"]) + 1):
        chrom = f"chrSynthetic{chromosome_index}"
        repeat_rows, truth_rows = repeats.get(chrom, []), truth.get(chrom, [])
        repeat_cursor = truth_cursor = 0
        for start in range(0, int(reference["chromosome_length_bp"]), BIN_SIZE):
            end = start + BIN_SIZE
            while repeat_cursor < len(repeat_rows) and repeat_rows[repeat_cursor][1] <= start:
                repeat_cursor += 1
            if end > int(reference["chromosome_length_bp"]) or (
                repeat_cursor < len(repeat_rows) and repeat_rows[repeat_cursor][0] < end
            ):
                continue
            while truth_cursor < len(truth_rows) and truth_rows[truth_cursor]["end"] <= start:
                truth_cursor += 1
            weighted = 0.0
            cursor = truth_cursor
            while cursor < len(truth_rows) and truth_rows[cursor]["start"] < end:
                row = truth_rows[cursor]
                weighted += max(0, min(end, row["end"]) - max(start, row["start"])) * row["signal"]
                cursor += 1
            rows.append((chrom, start, end, f"BIN_{len(rows) + 1:06d}", weighted / BIN_SIZE))
    with args.output_bed.open("w", encoding="utf-8", newline="\n") as handle:
        for chrom, start, end, identifier, _signal in rows:
            handle.write(f"{chrom}\t{start}\t{end}\t{identifier}\n")
    with args.expected_tsv.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("chrom\tstart\tend\tbin_id\texpected_signal\n")
        for chrom, start, end, identifier, signal in rows:
            handle.write(f"{chrom}\t{start}\t{end}\t{identifier}\t{signal:.8f}\n")


if __name__ == "__main__":
    main()
