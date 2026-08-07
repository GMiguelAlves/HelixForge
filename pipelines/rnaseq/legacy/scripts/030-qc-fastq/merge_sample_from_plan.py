#!/usr/bin/env python3
"""
Merge run-level trimmed FASTQs into one pair per biological sample.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import pandas as pd


def concatenate_gzip_members(inputs: list[Path], output: Path) -> None:
    """
    Concatenate gzip files without decompressing/recompressing.

    Gzip permits concatenated members, and standard tools used downstream
    (zcat/gzip, FastQC, Salmon, STAR) can read them correctly. This is much faster
    than opening FASTQs with gzip and recompressing the merged sample.
    """
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_suffix(output.suffix + ".tmp")
    with tmp.open("wb") as out_handle:
        for path in inputs:
            with path.open("rb") as in_handle:
                shutil.copyfileobj(in_handle, out_handle)
    tmp.replace(output)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--sample-id", required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    plan = pd.read_csv(args.plan, dtype=str, keep_default_na=False)
    sample = plan.loc[plan["sample_id"] == args.sample_id].copy()
    if sample.empty:
        raise ValueError(f"sample_id not found in plan: {args.sample_id}")

    sample = sample.sort_values("run_accession")
    r1_inputs = [Path(path) for path in sample["trimmed_run_r1"]]
    r2_inputs = [Path(path) for path in sample["trimmed_run_r2"]]
    r1_output = Path(sample["merged_sample_r1"].iloc[0])
    r2_output = Path(sample["merged_sample_r2"].iloc[0])

    missing = [str(path) for path in r1_inputs + r2_inputs if not path.exists()]
    if missing:
        raise FileNotFoundError(
            f"{len(missing)} trimmed run FASTQs are missing, e.g. "
            + ", ".join(missing[:10])
        )

    if not args.force and r1_output.exists() and r2_output.exists():
        print(f"[SKIP] Merged sample already exists: {args.sample_id}")
        return

    print(f"[INFO] Merging {len(sample)} runs for {args.sample_id}")
    concatenate_gzip_members(r1_inputs, r1_output)
    concatenate_gzip_members(r2_inputs, r2_output)
    print(f"[OK] Wrote {r1_output}")
    print(f"[OK] Wrote {r2_output}")


if __name__ == "__main__":
    main()
