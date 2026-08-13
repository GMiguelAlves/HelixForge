#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path


SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def clean(value: object) -> str:
    return str(value or "").strip()


def read_table(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    text = path.read_text(encoding="utf-8-sig")
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=",\t")
    except csv.Error:
        dialect = csv.excel_tab if path.suffix.lower() == ".tsv" else csv.excel
    reader = csv.DictReader(text.splitlines(), dialect=dialect)
    fields = list(reader.fieldnames or [])
    return fields, [{key: clean(value) for key, value in row.items()} for row in reader]


def read_settings(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return {
            clean(row.get("key")): clean(row.get("value"))
            for row in csv.DictReader(handle, delimiter="\t")
        }


def resolve_path(value: str, base: Path) -> Path:
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (base / path).resolve()


def first_existing(candidates: list[Path]) -> Path:
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]


def write_tsv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=fields, delimiter="\t", lineterminator="\n", extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(rows)


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def validate_reference(settings: dict[str, str], run_mode: str) -> dict[str, str]:
    transcriptome = clean(settings.get("REF_TRANSCRIPTS_FA"))
    annotation = clean(settings.get("REF_GTF")) or clean(settings.get("REF_GFF3"))
    genome = clean(settings.get("REF_GENOME_FA"))
    quant_method = clean(settings.get("QUANT_METHOD") or "salmon").lower()
    analysis_mode = clean(settings.get("NATIVE_ANALYSIS_MODE") or "quantification").lower()

    needs_salmon = False
    needs_star = False
    if run_mode in {"quant", "quantification"}:
        needs_salmon = True
    elif run_mode == "alignment":
        needs_star = True
    elif run_mode in {"import", "de", "differential_expression", "full"}:
        if analysis_mode == "both":
            needs_salmon = True
            needs_star = True
        elif analysis_mode == "alignment":
            needs_star = True
        elif analysis_mode == "config":
            needs_salmon = quant_method == "salmon"
            needs_star = quant_method == "star"
        else:
            needs_salmon = True
    if needs_salmon and not transcriptome:
        raise ValueError("REF_TRANSCRIPTS_FA is required by the Salmon production path")
    if (needs_salmon or needs_star) and not annotation:
        raise ValueError("REF_GTF or REF_GFF3 is required")
    if needs_star and not genome:
        raise ValueError("REF_GENOME_FA is required when the experimental STAR provider is selected")

    for label, value in (("transcriptome", transcriptome), ("annotation", annotation), ("genome", genome)):
        if value and not Path(value).is_file():
            raise ValueError(f"{label} reference does not exist: {value}")
    return {"genome": genome, "transcriptome": transcriptome, "annotation": annotation}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metadata", required=True, type=Path)
    parser.add_argument("--settings", required=True, type=Path)
    parser.add_argument("--normalized", required=True, type=Path)
    parser.add_argument("--plan-dir", required=True, type=Path)
    parser.add_argument("--reference-plan", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--trim-quality", default="")
    parser.add_argument("--trim-length", default="")
    parser.add_argument("--run-mode", default=os.environ.get("HELIXFORGE_RNASEQ_RUN_MODE", "full"))
    args = parser.parse_args()

    try:
        settings = read_settings(args.settings)
        fields, rows = read_table(args.metadata)
        required = {"dataset", "sample_id", "run_accession"}
        missing = sorted(required - set(fields))
        if missing:
            raise ValueError("metadata missing required columns: " + ", ".join(missing))
        if not rows:
            raise ValueError("metadata contains no records")

        configured_projects = [
            value for value in re.split(r"[\s,]+", clean(settings.get("PIPELINE_PROJECTS"))) if value
        ]
        projects = configured_projects or sorted({row["dataset"] for row in rows})
        unknown = sorted(set(projects) - {row["dataset"] for row in rows})
        if unknown:
            raise ValueError("no metadata records for configured project(s): " + ", ".join(unknown))

        scratch = clean(settings.get("SCRATCH_ROOT"))
        if not scratch:
            raise ValueError("SCRATCH_ROOT is required for deterministic output naming")
        scratch_root = Path(scratch).expanduser().resolve()
        metadata_base = Path(clean(settings.get("METADATA_BASE_DIR")) or args.metadata.parent).resolve()
        quality = clean(args.trim_quality) or clean(settings.get("TRIM_QUALITY"))
        length = clean(args.trim_length) or clean(settings.get("TRIM_LENGTH"))
        if not quality.isdigit() or not length.isdigit():
            raise ValueError("trim quality and length must be integers")

        seen_runs: set[str] = set()
        sample_prefixes: defaultdict[tuple[str, str], set[str]] = defaultdict(set)
        normalized: list[dict[str, str]] = []
        plans: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
        optional_missing: Counter[str] = Counter()

        for line, row in enumerate(rows, start=2):
            dataset = clean(row.get("dataset"))
            if dataset not in projects:
                continue
            sample = clean(row.get("sample_id"))
            run = clean(row.get("run_accession"))
            if not dataset or not sample or not run:
                raise ValueError(f"metadata row {line} has an empty required field")
            for label, value in (("dataset", dataset), ("sample_id", sample), ("run_accession", run)):
                if not SAFE_ID.fullmatch(value):
                    raise ValueError(f"row {line}: {label} contains unsupported characters: {value!r}")
            if run in seen_runs:
                raise ValueError(f"duplicated run_accession at row {line}: {run}")
            seen_runs.add(run)

            prefix = clean(row.get("file_prefix")) or sample
            sample_prefixes[(dataset, sample)].add(prefix)
            raw_dir = scratch_root / dataset / "fastq_ftp"
            explicit_r1 = clean(row.get("fastq_1")) or clean(row.get("raw_r1"))
            explicit_r2 = clean(row.get("fastq_2")) or clean(row.get("raw_r2"))
            raw_r1 = resolve_path(explicit_r1, metadata_base) if explicit_r1 else first_existing([
                raw_dir / f"{prefix}_{run}_R1.fastq.gz", raw_dir / f"{run}_1.fastq.gz"
            ])
            raw_r2 = resolve_path(explicit_r2, metadata_base) if explicit_r2 else first_existing([
                raw_dir / f"{prefix}_{run}_R2.fastq.gz", raw_dir / f"{run}_2.fastq.gz"
            ])
            for label, path in (("fastq_1", raw_r1), ("fastq_2", raw_r2)):
                if not path.is_file():
                    raise ValueError(f"row {line}: {label} does not exist: {path}")
            if raw_r1 == raw_r2:
                raise ValueError(f"row {line}: fastq_1 and fastq_2 resolve to the same file")

            normalized_row = dict(row)
            normalized_row.update({
                "dataset": dataset, "sample_id": sample, "run_accession": run,
                "file_prefix": prefix, "fastq_1": str(raw_r1), "fastq_2": str(raw_r2),
            })
            normalized.append(normalized_row)
            for field in ("condition", "batch"):
                if field in fields and not clean(row.get(field)):
                    optional_missing[field] += 1

            trimmed_dir = scratch_root / dataset / "trimmed_runs"
            merged_dir = scratch_root / dataset / "trimmed_merged"
            plans[dataset].append({
                "dataset": dataset,
                "sample_id": sample,
                "file_prefix": prefix,
                "run_accession": run,
                "raw_r1": str(raw_r1),
                "raw_r2": str(raw_r2),
                "trimmed_run_r1": str(trimmed_dir / f"{prefix}_{run}_R1_trimmed.fastq.gz"),
                "trimmed_run_r2": str(trimmed_dir / f"{prefix}_{run}_R2_trimmed.fastq.gz"),
                "merged_sample_r1": str(merged_dir / f"{sample}_R1_trimmed.fastq.gz"),
                "merged_sample_r2": str(merged_dir / f"{sample}_R2_trimmed.fastq.gz"),
                "trim_quality": quality,
                "trim_length": length,
            })

        inconsistent = [f"{dataset}/{sample}" for (dataset, sample), values in sample_prefixes.items() if len(values) > 1]
        if inconsistent:
            raise ValueError("samples have inconsistent file_prefix values: " + ", ".join(inconsistent))

        normalized_fields = list(fields)
        for field in ("file_prefix", "fastq_1", "fastq_2"):
            if field not in normalized_fields:
                normalized_fields.append(field)
        normalized.sort(key=lambda row: (row["dataset"], row["sample_id"], row["run_accession"]))
        write_csv(args.normalized, normalized, normalized_fields)

        plan_fields = [
            "dataset", "sample_id", "file_prefix", "run_accession", "raw_r1", "raw_r2",
            "trimmed_run_r1", "trimmed_run_r2", "merged_sample_r1", "merged_sample_r2",
            "trim_quality", "trim_length",
        ]
        for dataset in projects:
            dataset_rows = sorted(plans[dataset], key=lambda row: (row["sample_id"], row["run_accession"]))
            safe_dataset = re.sub(r"[^A-Za-z0-9_.-]", "_", dataset)
            path = args.plan_dir / f"{safe_dataset}_qc_plan.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=plan_fields, lineterminator="\n")
                writer.writeheader()
                writer.writerows(dataset_rows)

        references = validate_reference(settings, args.run_mode.lower())
        write_tsv(args.reference_plan, [{
            "reference_id": clean(settings.get("ORGANISM_NAME")) or "rnaseq-reference",
            "organism": clean(settings.get("ORGANISM_NAME")),
            **references,
        }], ["reference_id", "organism", "genome", "transcriptome", "annotation"])

        report = {
            "schema_version": "1.0", "status": "valid", "rows": len(normalized),
            "biological_samples": len({(row["dataset"], row["sample_id"]) for row in normalized}),
            "datasets": projects, "technical_runs_per_sample": {
                f"{dataset}/{sample}": sum(
                    row["dataset"] == dataset and row["sample_id"] == sample for row in normalized
                )
                for dataset, sample in sorted({(row["dataset"], row["sample_id"]) for row in normalized})
            },
            "optional_missing_values": dict(sorted(optional_missing.items())),
            "download_performed": False,
        }
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"validated {len(normalized)} technical runs across {len(projects)} dataset(s)")
        return 0
    except (OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
