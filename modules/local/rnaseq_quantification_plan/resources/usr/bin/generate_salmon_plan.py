#!/usr/bin/env python3
"""
Create a sample-level Salmon quantification plan from a step-030 qc_plan.

Input qc_plan has one row per technical run. Salmon should run once per
biological sample, using the merged FASTQs generated in step 030.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path, PurePosixPath

import pandas as pd


def load_plan(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def as_pipeline_path(value: str | Path):
    text = str(value)
    if "\\" in text or (len(text) >= 2 and text[1] == ":"):
        return Path(text)
    return PurePosixPath(text)


def path_exists(path: str) -> bool:
    return Path(path).exists()


def build_salmon_plan(
    qc_plan: pd.DataFrame,
    project: str,
    output_root,
) -> pd.DataFrame:
    required = {"dataset", "sample_id", "merged_sample_r1", "merged_sample_r2"}
    missing = sorted(required - set(qc_plan.columns))
    if missing:
        raise ValueError(f"qc_plan missing required columns: {', '.join(missing)}")

    df = qc_plan.loc[qc_plan["dataset"] == project].copy()
    if df.empty:
        raise ValueError(f"no rows found for project {project}")

    sample_rows = (
        df[["dataset", "sample_id", "merged_sample_r1", "merged_sample_r2"]]
        .drop_duplicates()
        .sort_values("sample_id")
        .reset_index(drop=True)
    )

    if sample_rows["sample_id"].duplicated().any():
        duplicated = sorted(
            sample_rows.loc[sample_rows["sample_id"].duplicated(), "sample_id"].unique()
        )
        raise ValueError("duplicated sample_id in sample-level plan: " + ", ".join(duplicated[:10]))

    sample_rows["quant_dir"] = sample_rows["sample_id"].apply(
        lambda sample: str(output_root / project / sample)
    )
    sample_rows["num_runs"] = sample_rows["sample_id"].map(
        df.groupby("sample_id")["run_accession"].nunique()
    )

    return sample_rows[
        [
            "dataset",
            "sample_id",
            "num_runs",
            "merged_sample_r1",
            "merged_sample_r2",
            "quant_dir",
        ]
    ]


def validate_plan(plan: pd.DataFrame, allow_missing: bool) -> None:
    missing = []
    for col in ["merged_sample_r1", "merged_sample_r2"]:
        missing.extend(path for path in plan[col] if not path_exists(path))

    if missing and not allow_missing:
        raise FileNotFoundError(
            f"{len(missing)} merged FASTQs are missing, e.g. "
            + ", ".join(str(path) for path in missing[:10])
        )

    if missing:
        print(
            f"[WARN] {len(missing)} merged FASTQs are missing; plan was written anyway.",
            flush=True,
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--qc-plan", required=True, type=Path)
    parser.add_argument("--project", required=True)
    parser.add_argument("--output-root", default=os.environ.get("QUANT_DIR", "quants"))
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--allow-missing", action="store_true")
    args = parser.parse_args()

    qc_plan = load_plan(args.qc_plan)
    salmon_plan = build_salmon_plan(qc_plan, args.project, as_pipeline_path(args.output_root))
    validate_plan(salmon_plan, args.allow_missing)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    salmon_plan.to_csv(args.output, index=False)

    print(f"Wrote Salmon plan: {args.output}")
    print(f"Samples: {len(salmon_plan)}")


if __name__ == "__main__":
    main()
