#!/usr/bin/env python3
"""
Create a run-level QC/trimming plan from the final parsed metadata.

The plan is the contract for step 030. Each row is one technical run, with
absolute paths for raw FASTQs, run-level trimmed FASTQs, and merged sample FASTQs.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path, PurePosixPath

import pandas as pd


def load_metadata(path: Path) -> pd.DataFrame:
    sep = "\t" if path.suffix.lower() == ".tsv" else ","
    return pd.read_csv(path, sep=sep, dtype=str, keep_default_na=False)


def as_pipeline_path(value: str | Path | None):
    if value is None:
        return None
    text = str(value)
    if text.startswith("/"):
        return PurePosixPath(text)
    return Path(text)


def path_exists(path) -> bool:
    return Path(str(path)).exists()


def first_existing(paths: list) -> object:
    for path in paths:
        if path_exists(path):
            return path
    return paths[0]


def build_plan(
    metadata: pd.DataFrame,
    project: str,
    scratch_root,
    raw_dir,
    trimmed_runs_dir,
    merged_dir,
) -> pd.DataFrame:
    required = {"dataset", "sample_id", "run_accession"}
    missing = sorted(required - set(metadata.columns))
    if missing:
        raise ValueError(f"metadata missing required columns: {', '.join(missing)}")

    df = metadata.loc[metadata["dataset"] == project].copy()
    if df.empty:
        raise ValueError(f"no metadata rows found for project {project}")

    if df["run_accession"].duplicated().any():
        duplicated = sorted(df.loc[df["run_accession"].duplicated(), "run_accession"].unique())
        raise ValueError("duplicated run_accession values: " + ", ".join(duplicated[:10]))

    prefix_col = "file_prefix" if "file_prefix" in df.columns else "sample_id"
    raw_dir = raw_dir or scratch_root / project / "fastq_ftp"
    trimmed_runs_dir = trimmed_runs_dir or scratch_root / project / "trimmed_runs"
    merged_dir = merged_dir or scratch_root / project / "trimmed_merged"

    rows = []
    for _, row in df.sort_values(["sample_id", "run_accession"]).iterrows():
        sample_id = row["sample_id"]
        run = row["run_accession"]
        prefix = row[prefix_col] or sample_id

        renamed_r1 = raw_dir / f"{prefix}_{run}_R1.fastq.gz"
        renamed_r2 = raw_dir / f"{prefix}_{run}_R2.fastq.gz"
        original_r1 = raw_dir / f"{run}_1.fastq.gz"
        original_r2 = raw_dir / f"{run}_2.fastq.gz"

        raw_r1 = first_existing([renamed_r1, original_r1])
        raw_r2 = first_existing([renamed_r2, original_r2])

        rows.append(
            {
                "dataset": project,
                "sample_id": sample_id,
                "file_prefix": prefix,
                "run_accession": run,
                "raw_r1": str(raw_r1),
                "raw_r2": str(raw_r2),
                "trimmed_run_r1": str(trimmed_runs_dir / f"{prefix}_{run}_R1_trimmed.fastq.gz"),
                "trimmed_run_r2": str(trimmed_runs_dir / f"{prefix}_{run}_R2_trimmed.fastq.gz"),
                "merged_sample_r1": str(merged_dir / f"{sample_id}_R1_trimmed.fastq.gz"),
                "merged_sample_r2": str(merged_dir / f"{sample_id}_R2_trimmed.fastq.gz"),
            }
        )

    return pd.DataFrame(rows)


def validate_plan(plan: pd.DataFrame, allow_missing: bool) -> None:
    missing = []
    for col in ["raw_r1", "raw_r2"]:
        missing.extend(path for path in plan[col] if not path_exists(path))

    duplicated_outputs = []
    for col in ["trimmed_run_r1", "trimmed_run_r2"]:
        duplicated_outputs.extend(plan.loc[plan[col].duplicated(), col].tolist())

    if duplicated_outputs:
        raise ValueError("duplicated output paths: " + ", ".join(duplicated_outputs[:10]))

    if missing and not allow_missing:
        raise FileNotFoundError(
            f"{len(missing)} raw FASTQs are missing, e.g. "
            + ", ".join(str(path) for path in missing[:10])
        )

    if missing:
        print(
            f"[WARN] {len(missing)} raw FASTQs are missing; plan was written anyway.",
            flush=True,
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metadata", required=True, type=Path)
    parser.add_argument("--project", required=True)
    parser.add_argument("--scratch-root", default=os.environ.get("SCRATCH_ROOT"))
    parser.add_argument("--raw-dir", default=None)
    parser.add_argument("--trimmed-runs-dir", default=None)
    parser.add_argument("--merged-dir", default=None)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--allow-missing", action="store_true")
    args = parser.parse_args()

    if args.scratch_root is None and not (args.raw_dir and args.trimmed_runs_dir and args.merged_dir):
        raise ValueError("Provide --scratch-root or export SCRATCH_ROOT before running this script.")

    metadata = load_metadata(args.metadata)
    plan = build_plan(
        metadata=metadata,
        project=args.project,
        scratch_root=as_pipeline_path(args.scratch_root),
        raw_dir=as_pipeline_path(args.raw_dir),
        trimmed_runs_dir=as_pipeline_path(args.trimmed_runs_dir),
        merged_dir=as_pipeline_path(args.merged_dir),
    )
    validate_plan(plan, args.allow_missing)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    plan.to_csv(args.output, index=False)

    print(f"Wrote QC plan: {args.output}")
    print(f"Rows/runs: {len(plan)}")
    print(f"Biological samples: {plan['sample_id'].nunique()}")


if __name__ == "__main__":
    main()
