#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def read_metadata(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    text = path.read_text(encoding="utf-8-sig")
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=",\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(text.splitlines(), dialect=dialect)
    if reader.fieldnames is None:
        raise ValueError("metadata has no header")
    return list(reader.fieldnames), [dict(row) for row in reader]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metadata", required=True, type=Path)
    parser.add_argument("--provider", required=True, choices=("salmon", "star"))
    parser.add_argument("--project", default="")
    parser.add_argument("--star-count-column", default="unstranded")
    parser.add_argument("--allow-missing", action="store_true")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("sources", nargs="+", type=Path)
    args = parser.parse_args()

    fields, metadata = read_metadata(args.metadata)
    missing_fields = [name for name in ("dataset", "sample_id") if name not in fields]
    if missing_fields:
        raise ValueError("metadata missing required columns: " + ", ".join(missing_fields))

    source_by_key: dict[tuple[str, str], dict[str, object]] = {}
    for source_dir in args.sources:
        source = json.loads((source_dir / "source.json").read_text(encoding="utf-8"))
        if source["provider"] != args.provider:
            raise ValueError(f"unexpected provider in {source_dir}: {source['provider']}")
        key = (str(source["dataset"]), str(source["sample_id"]))
        if key in source_by_key:
            raise ValueError(f"duplicated import source: {key[0]}/{key[1]}")
        source_by_key[key] = source

    selected: list[dict[str, str]] = []
    seen: dict[tuple[str, str], dict[str, str]] = {}
    seen_runs: set[str] = set()
    for line_number, row in enumerate(metadata, start=2):
        key = ((row.get("dataset") or "").strip(), (row.get("sample_id") or "").strip())
        if not key[0] or not key[1]:
            raise ValueError(
                f"metadata row {line_number} has an empty dataset or sample_id"
            )
        if key in seen:
            run = (row.get("run_accession") or "").strip()
            if "run_accession" not in fields or not run:
                raise ValueError(f"duplicated metadata sample at row {line_number}: {key[0]}/{key[1]}")
            if run in seen_runs:
                raise ValueError(f"duplicated run_accession at row {line_number}: {run}")
            run_specific = {"run_accession", "lane"}
            conflicts = [
                field for field in fields
                if field not in run_specific
                and not field.startswith(("fastq_", "raw_", "trimmed_", "quant_", "__"))
                and (seen[key].get(field) or "").strip() != (row.get(field) or "").strip()
            ]
            if conflicts:
                raise ValueError(
                    f"inconsistent metadata across technical runs for {key[0]}/{key[1]}: "
                    + ", ".join(conflicts)
                )
            seen_runs.add(run)
            continue
        if args.project and key[0] != args.project:
            continue
        seen[key] = row
        run = (row.get("run_accession") or "").strip()
        if run:
            if run in seen_runs:
                raise ValueError(f"duplicated run_accession at row {line_number}: {run}")
            seen_runs.add(run)
        source = source_by_key.get(key)
        if source is None:
            if args.allow_missing:
                continue
            raise ValueError(f"provider artifact missing for {key[0]}/{key[1]}")
        import_id = key[1] if args.project else f"{key[0]}__{key[1]}"
        out = dict(row)
        out["dataset"] = key[0]
        out["sample_id"] = key[1]
        out["import_id"] = import_id
        out["quant_file"] = str(source.get("compatibility_path", ""))
        out["quant_exists"] = "TRUE" if args.provider == "salmon" else "True"
        if args.provider == "star":
            out["quant_method"] = "star"
            out["expression_unit"] = "CPM"
            out["star_count_column"] = args.star_count_column
        out["__source_name"] = str(source["source_name"])
        out["__manifest_sha256"] = str(source.get("provider_manifest_sha256", ""))
        selected.append(out)

    if not selected:
        raise ValueError("no provider artifacts available to import")
    selected.sort(key=lambda row: (row["dataset"], row["sample_id"]))
    import_ids = [row["import_id"] for row in selected]
    if len(import_ids) != len(set(import_ids)):
        raise ValueError("duplicated import_id values")

    output_fields = fields + ["import_id", "quant_file", "quant_exists"]
    if args.provider == "star":
        output_fields += ["quant_method", "expression_unit", "star_count_column"]
    output_fields += ["__source_name", "__manifest_sha256"]
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=output_fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(selected)

    print(json.dumps({"provider": args.provider, "samples": len(selected), "import_ids": import_ids}))


if __name__ == "__main__":
    main()
