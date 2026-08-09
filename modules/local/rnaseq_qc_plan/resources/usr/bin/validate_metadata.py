#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metadata", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    text = args.metadata.read_text(encoding="utf-8-sig")
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=",\t")
    except csv.Error:
        dialect = csv.excel_tab if args.metadata.suffix.lower() == ".tsv" else csv.excel
    reader = csv.DictReader(text.splitlines(), dialect=dialect)
    fields = list(reader.fieldnames or [])
    required = ["dataset", "sample_id", "run_accession"]
    missing_columns = [field for field in required if field not in fields]
    if missing_columns:
        raise ValueError("metadata missing required columns: " + ", ".join(missing_columns))

    rows = [dict(row) for row in reader]
    if not rows:
        raise ValueError("metadata contains no samples")
    runs: set[str] = set()
    sample_runs: defaultdict[tuple[str, str], int] = defaultdict(int)
    prefixes: defaultdict[tuple[str, str], set[str]] = defaultdict(set)
    missing_optional = Counter()
    for line_number, row in enumerate(rows, start=2):
        values = {field: (row.get(field) or "").strip() for field in fields}
        blank = [field for field in required if not values[field]]
        if blank:
            raise ValueError(f"metadata row {line_number} has empty required fields: {', '.join(blank)}")
        run = values["run_accession"]
        if run in runs:
            raise ValueError(f"duplicated run_accession at row {line_number}: {run}")
        runs.add(run)
        key = (values["dataset"], values["sample_id"])
        sample_runs[key] += 1
        if "file_prefix" in fields and values["file_prefix"]:
            prefixes[key].add(values["file_prefix"])
        for field in ("condition", "sex", "stage", "batch", "lane"):
            if field in fields and not values[field]:
                missing_optional[field] += 1
    inconsistent = [f"{dataset}/{sample}" for (dataset, sample), values in prefixes.items() if len(values) > 1]
    if inconsistent:
        raise ValueError("samples have inconsistent file_prefix values: " + ", ".join(inconsistent[:20]))

    report = {
        "schema_version": "1.0", "status": "valid", "rows": len(rows),
        "biological_samples": len(sample_runs), "datasets": len({key[0] for key in sample_runs}),
        "technical_runs_per_sample": {f"{key[0]}/{key[1]}": value for key, value in sorted(sample_runs.items())},
        "optional_fields_present": [field for field in ("condition", "sex", "stage", "batch", "lane") if field in fields],
        "optional_missing_values": dict(sorted(missing_optional.items())),
    }
    args.output.write_text(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
