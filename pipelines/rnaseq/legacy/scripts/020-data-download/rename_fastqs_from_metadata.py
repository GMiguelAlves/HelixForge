#!/usr/bin/env python3
"""
Verify and rename downloaded FASTQs using parsed metadata.

Default mode is a dry run. Use --apply only after the validation summary looks
right. Expected input files are ENA/SRA names like ERR506074_1.fastq.gz and
ERR506074_2.fastq.gz.
"""

from __future__ import annotations

import argparse
import csv
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd


@dataclass(frozen=True)
class RenamePlan:
    run_accession: str
    sample_id: str
    read: str
    source: Path
    target: Path


def load_metadata(path: Path) -> pd.DataFrame:
    sep = "\t" if path.suffix.lower() == ".tsv" else ","
    return pd.read_csv(path, sep=sep, dtype=str, keep_default_na=False)


def normalize_read_suffixes(layout: str) -> tuple[str, ...]:
    if layout == "paired":
        return ("1", "2")
    if layout == "single":
        return ("1",)
    raise ValueError("--layout must be 'paired' or 'single'")


def build_plan(
    metadata: pd.DataFrame,
    project: str,
    fastq_dir: Path,
    layout: str,
) -> list[RenamePlan]:
    required = {"dataset", "sample_id", "run_accession"}
    missing = sorted(required - set(metadata.columns))
    if missing:
        raise ValueError(f"metadata missing required columns: {', '.join(missing)}")

    project_df = metadata.loc[metadata["dataset"] == project].copy()
    if project_df.empty:
        raise ValueError(f"no metadata rows found for project {project}")

    prefix_col = "file_prefix" if "file_prefix" in project_df.columns else "sample_id"
    read_suffixes = normalize_read_suffixes(layout)
    plan: list[RenamePlan] = []

    seen_runs = set()
    for _, row in project_df.iterrows():
        run = row["run_accession"].strip()
        sample_id = row["sample_id"].strip()
        prefix = row[prefix_col].strip() or sample_id

        if not run:
            raise ValueError(f"empty run_accession in project {project}")
        if run in seen_runs:
            raise ValueError(f"duplicated run_accession in metadata: {run}")
        seen_runs.add(run)

        for read in read_suffixes:
            source = fastq_dir / f"{run}_{read}.fastq.gz"
            target = fastq_dir / f"{prefix}_{run}_R{read}.fastq.gz"
            plan.append(
                RenamePlan(
                    run_accession=run,
                    sample_id=sample_id,
                    read=f"R{read}",
                    source=source,
                    target=target,
                )
            )

    return plan


def find_fastqs(fastq_dir: Path) -> set[Path]:
    return {path for path in fastq_dir.glob("*.fastq.gz") if path.is_file()}


def validate_plan(
    plan: Iterable[RenamePlan],
    fastq_dir: Path,
    allow_extra: bool,
) -> tuple[list[str], list[str]]:
    plan = list(plan)
    errors: list[str] = []
    warnings: list[str] = []

    sources = [item.source for item in plan]
    targets = [item.target for item in plan]

    duplicate_sources = sorted({p.name for p in sources if sources.count(p) > 1})
    duplicate_targets = sorted({p.name for p in targets if targets.count(p) > 1})

    if duplicate_sources:
        errors.append("duplicate source names in plan: " + ", ".join(duplicate_sources[:10]))
    if duplicate_targets:
        errors.append("duplicate target names in plan: " + ", ".join(duplicate_targets[:10]))

    missing_sources = [p.name for p in sources if not p.exists()]
    if missing_sources:
        errors.append(
            f"{len(missing_sources)} expected FASTQs are missing, e.g. "
            + ", ".join(missing_sources[:10])
        )

    existing_targets = [
        p.name for p in targets
        if p.exists() and p not in sources
    ]
    if existing_targets:
        errors.append(
            f"{len(existing_targets)} target filenames already exist, e.g. "
            + ", ".join(existing_targets[:10])
        )

    source_set = set(sources)
    target_set = set(targets)
    observed_fastqs = find_fastqs(fastq_dir)
    expected_or_new = source_set | target_set
    extras = sorted(p.name for p in observed_fastqs - expected_or_new)

    if extras and allow_extra:
        warnings.append(
            f"{len(extras)} extra FASTQs in directory will be ignored, e.g. "
            + ", ".join(extras[:10])
        )
    elif extras:
        errors.append(
            f"{len(extras)} extra FASTQs found; pass --allow-extra to ignore, e.g. "
            + ", ".join(extras[:10])
        )

    return errors, warnings


def write_manifest(plan: Iterable[RenamePlan], manifest: Path) -> None:
    manifest.parent.mkdir(parents=True, exist_ok=True)
    with manifest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "sample_id",
                "run_accession",
                "read",
                "old_filename",
                "new_filename",
            ],
        )
        writer.writeheader()
        for item in plan:
            writer.writerow(
                {
                    "sample_id": item.sample_id,
                    "run_accession": item.run_accession,
                    "read": item.read,
                    "old_filename": item.source.name,
                    "new_filename": item.target.name,
                }
            )


def apply_plan(plan: Iterable[RenamePlan]) -> None:
    for item in plan:
        item.source.rename(item.target)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metadata", required=True, type=Path)
    parser.add_argument("--project", required=True)
    parser.add_argument(
        "--scratch-root",
        type=Path,
        default=Path(os.environ.get("SCRATCH_ROOT", "work/scratch")),
        help="Directory containing <PROJECT>/fastq_ftp",
    )
    parser.add_argument("--fastq-dir", type=Path, default=None)
    parser.add_argument("--layout", choices=["paired", "single"], default="paired")
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--allow-extra", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    fastq_dir = args.fastq_dir or args.scratch_root / args.project / "fastq_ftp"
    if not fastq_dir.exists():
        raise FileNotFoundError(f"FASTQ directory not found: {fastq_dir}")

    metadata = load_metadata(args.metadata)
    plan = build_plan(metadata, args.project, fastq_dir, args.layout)
    errors, warnings = validate_plan(plan, fastq_dir, args.allow_extra)

    print(f"Project: {args.project}")
    print(f"FASTQ directory: {fastq_dir}")
    print(f"Planned renames: {len(plan)}")
    print(f"Mode: {'APPLY' if args.apply else 'DRY RUN'}")

    for warning in warnings:
        print(f"[WARN] {warning}")

    if errors:
        print("[FAIL] Validation failed:")
        for error in errors:
            print(f"  - {error}")
        raise SystemExit(1)

    if args.manifest:
        write_manifest(plan, args.manifest)
        print(f"Manifest written: {args.manifest}")

    preview = plan[:5]
    if preview:
        print("Preview:")
        for item in preview:
            print(f"  {item.source.name} -> {item.target.name}")

    if args.apply:
        apply_plan(plan)
        print("[OK] Renaming completed.")
    else:
        print("[OK] Dry run passed. Re-run with --apply to rename files.")


if __name__ == "__main__":
    main()
