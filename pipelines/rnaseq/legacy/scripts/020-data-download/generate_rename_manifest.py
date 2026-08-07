#!/usr/bin/env python3
"""
Generate a run-level FASTQ rename manifest from parsed metadata.

The manifest is intentionally non-destructive. Review it, then use it as input
for a separate rename/copy step on the downloaded FASTQs.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def load_metadata(path: Path) -> pd.DataFrame:
    sep = "\t" if path.suffix.lower() == ".tsv" else ","
    return pd.read_csv(path, sep=sep, dtype=str, keep_default_na=False)


def build_manifest(metadata: pd.DataFrame, project: str | None) -> pd.DataFrame:
    if project:
        metadata = metadata.loc[metadata["dataset"] == project].copy()

    required = {"run_accession", "sample_id"}
    missing = sorted(required - set(metadata.columns))
    if missing:
        raise ValueError(f"Metadata missing required columns: {', '.join(missing)}")

    prefix_col = "file_prefix" if "file_prefix" in metadata.columns else "sample_id"
    rows = []

    for _, row in metadata.iterrows():
        run = row["run_accession"]
        prefix = row[prefix_col] or row["sample_id"]

        if not run or not prefix:
            continue

        for read in ("1", "2"):
            rows.append(
                {
                    "dataset": row.get("dataset", ""),
                    "sample_id": row["sample_id"],
                    "run_accession": run,
                    "read": f"R{read}",
                    "old_filename": f"{run}_{read}.fastq.gz",
                    "new_filename": f"{prefix}_{run}_R{read}.fastq.gz",
                }
            )

    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metadata", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--project", default=None)
    args = parser.parse_args()

    metadata = load_metadata(args.metadata)
    manifest = build_manifest(metadata, args.project)
    manifest.to_csv(args.output, index=False)

    print(f"Wrote {len(manifest)} rename rows to {args.output}")


if __name__ == "__main__":
    main()
