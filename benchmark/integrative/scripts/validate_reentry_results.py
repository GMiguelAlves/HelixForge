#!/usr/bin/env python3
"""Administrative validation for compact 10C results."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    results, report = args.results.resolve(), args.report.resolve()
    for path in results.glob("*.json"):
        json.loads(path.read_text(encoding="utf-8"))
    for path in results.glob("*.tsv"):
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle, delimiter="\t"))
        assert rows, f"empty TSV: {path.name}"
        assert all(None not in row for row in rows), f"ragged TSV: {path.name}"
    for line in (results / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        expected, name = line.split("  ", 1)
        path = report if name == report.name else results / name
        assert path.is_file(), f"missing checksum target: {name}"
        assert sha256(path) == expected, f"checksum mismatch: {name}"
    summary = json.loads((results / "benchmark_summary.json").read_text(encoding="utf-8"))
    assert summary["reentry_equivalence_benchmark"] in {"PASS", "FAIL"}
    report_text = report.read_text(encoding="utf-8")
    assert report_text.rstrip().endswith(summary["readiness"])
    forbidden = ("/scratch/", "/home/ra", "C:\\Users\\")
    for path in [report, *results.glob("*.json")]:
        text = path.read_text(encoding="utf-8")
        assert not any(token in text for token in forbidden), f"machine path leaked: {path.name}"
    assert max(path.stat().st_size for path in results.iterdir() if path.is_file()) < 5 * 1024 * 1024
    print("integrative re-entry results: valid")


if __name__ == "__main__":
    main()
