#!/usr/bin/env python3
"""Add legacy trimming parameters to a Nextflow-owned copy of a QC plan."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--quality", required=True)
    parser.add_argument("--length", required=True)
    args = parser.parse_args()

    with args.plan.open(newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])

    for column in ("trim_quality", "trim_length"):
        if column not in fieldnames:
            fieldnames.append(column)

    for row in rows:
        row["trim_quality"] = args.quality
        row["trim_length"] = args.length

    temporary = args.plan.with_suffix(args.plan.suffix + ".tmp")
    with temporary.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(args.plan)


if __name__ == "__main__":
    main()
