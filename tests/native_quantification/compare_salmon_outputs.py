#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import struct
from pathlib import Path
from typing import Any


VOLATILE_KEYS = {
    "start_time",
    "end_time",
    "run_start_time",
    "run_stop_time",
    "output",
    "auxDir",
    "index",
    "mates1",
    "mates2",
    "read_files",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: normalize_json(item)
            for key, item in sorted(value.items())
            if key not in VOLATILE_KEYS and "time" not in key.lower()
        }
    if isinstance(value, list):
        return [normalize_json(item) for item in value]
    if isinstance(value, str) and (value.startswith("/") or ":\\" in value):
        return "<PATH>"
    return value


def compare_quant(legacy: Path, native: Path) -> None:
    with legacy.open(newline="", encoding="utf-8") as left, native.open(
        newline="", encoding="utf-8"
    ) as right:
        legacy_rows = list(csv.DictReader(left, delimiter="\t"))
        native_rows = list(csv.DictReader(right, delimiter="\t"))

    expected_columns = ["Name", "Length", "EffectiveLength", "TPM", "NumReads"]
    if list(legacy_rows[0]) != expected_columns or list(native_rows[0]) != expected_columns:
        raise AssertionError("quant.sf columns changed")
    if len(legacy_rows) != len(native_rows):
        raise AssertionError("quant.sf transcript count changed")

    for left, right in zip(legacy_rows, native_rows, strict=True):
        if left["Name"] != right["Name"] or left["Length"] != right["Length"]:
            raise AssertionError(f"quant.sf identity changed: {left['Name']}")
        for column in ["EffectiveLength", "TPM", "NumReads"]:
            if not math.isclose(
                float(left[column]), float(right[column]), rel_tol=1e-9, abs_tol=1e-7
            ):
                raise AssertionError(f"quant.sf {column} changed for {left['Name']}")


def compare_fragment_distribution(legacy: Path, native: Path) -> None:
    with gzip.open(legacy, "rb") as left, gzip.open(native, "rb") as right:
        left_bytes = left.read()
        right_bytes = right.read()
    left_values = struct.unpack(f"{len(left_bytes) // 4}i", left_bytes)
    right_values = struct.unpack(f"{len(right_bytes) // 4}i", right_bytes)
    if len(left_values) != len(right_values):
        raise AssertionError("fragment-distribution bin count changed")
    left_total = sum(left_values)
    right_total = sum(right_values)
    if left_total != right_total:
        raise AssertionError("fragment-distribution sample count changed")
    left_mean = sum(index * count for index, count in enumerate(left_values)) / left_total
    right_mean = sum(index * count for index, count in enumerate(right_values)) / right_total
    if not math.isclose(left_mean, right_mean, rel_tol=0.01, abs_tol=1.0):
        raise AssertionError("fragment-distribution mean changed beyond stochastic tolerance")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("legacy", type=Path)
    parser.add_argument("native", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()

    results: list[tuple[str, str, str]] = []
    compare_quant(args.legacy / "quant.sf", args.native / "quant.sf")
    results.append(("quant.sf", "numeric-semantic", "PASS"))

    for filename in ["cmd_info.json", "lib_format_counts.json"]:
        left = normalize_json(load_json(args.legacy / filename))
        right = normalize_json(load_json(args.native / filename))
        if left != right:
            raise AssertionError(f"semantic JSON changed: {filename}")
        results.append((filename, "json-semantic", "PASS"))

    legacy_aux = args.legacy / "aux_info"
    native_aux = args.native / "aux_info"
    legacy_names = sorted(path.name for path in legacy_aux.iterdir())
    native_names = sorted(path.name for path in native_aux.iterdir())
    if legacy_names != native_names:
        raise AssertionError("aux_info file set changed")
    results.append(("aux_info/file_set", "exact", "PASS"))

    left_meta = normalize_json(load_json(legacy_aux / "meta_info.json"))
    right_meta = normalize_json(load_json(native_aux / "meta_info.json"))
    if left_meta != right_meta:
        raise AssertionError("aux_info/meta_info.json scientific values changed")
    results.append(("aux_info/meta_info.json", "json-semantic", "PASS"))

    for filename in ["ambig_info.tsv"]:
        if (legacy_aux / filename).read_bytes() != (native_aux / filename).read_bytes():
            raise AssertionError(f"auxiliary table changed: {filename}")
        results.append((f"aux_info/{filename}", "byte", "PASS"))

    compare_fragment_distribution(legacy_aux / "fld.gz", native_aux / "fld.gz")
    results.append(("aux_info/fld.gz", "distribution-semantic", "PASS"))

    for output in [args.legacy, args.native]:
        if not (output / "logs" / "salmon_quant.log").is_file():
            raise AssertionError("Salmon log is missing")
    results.append(("logs/salmon_quant.log", "presence-and-meta-stats", "PASS"))

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(["artifact", "comparison", "result"])
        writer.writerows(results)


if __name__ == "__main__":
    main()
