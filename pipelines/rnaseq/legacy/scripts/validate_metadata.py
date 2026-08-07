#!/usr/bin/env python3
"""Validate the final RNA-seq metadata contract."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


REQUIRED_COLUMNS = {"dataset", "sample_id", "run_accession"}


def read_table(path: Path) -> pd.DataFrame:
    sep = "\t" if path.suffix.lower() == ".tsv" else ","
    return pd.read_csv(path, sep=sep, dtype=str, keep_default_na=False)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metadata", required=True, type=Path)
    parser.add_argument("--allow-missing", action="store_true")
    args = parser.parse_args()

    if not args.metadata.exists():
        if args.allow_missing:
            print(f"[WARN] Metadata not found yet: {args.metadata}")
            return
        raise FileNotFoundError(f"Metadata not found: {args.metadata}")

    metadata = read_table(args.metadata)
    missing = sorted(REQUIRED_COLUMNS - set(metadata.columns))
    if missing:
        raise SystemExit("[ERROR] Missing required columns: " + ", ".join(missing))

    empty = [
        column
        for column in sorted(REQUIRED_COLUMNS)
        if metadata[column].astype(str).str.strip().eq("").any()
    ]
    if empty:
        raise SystemExit("[ERROR] Empty values in required columns: " + ", ".join(empty))

    duplicated = metadata["run_accession"].duplicated()
    if duplicated.any():
        examples = ", ".join(metadata.loc[duplicated, "run_accession"].head(10))
        raise SystemExit(f"[ERROR] Duplicated run_accession values, e.g. {examples}")

    print(f"[OK] Metadata validated: {args.metadata}")
    print(f"[OK] Rows: {len(metadata)}")
    print(f"[OK] Projects: {metadata['dataset'].nunique()}")
    print(f"[OK] Samples: {metadata['sample_id'].nunique()}")


if __name__ == "__main__":
    main()

