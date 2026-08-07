#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import OrderedDict
from pathlib import Path


COUNT_COLUMNS = {
    "unstranded": 1,
    "2": 1,
    "stranded_forward": 2,
    "3": 2,
    "stranded_reverse": 3,
    "4": 3,
}
COUNT_NAMES = {1: "unstranded", 2: "stranded_forward", 3: "stranded_reverse"}


def read_table(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if reader.fieldnames is None:
            raise ValueError("sample table has no header")
        return list(reader.fieldnames), [dict(row) for row in reader]


def read_counts(path: Path, column: int) -> OrderedDict[str, int]:
    values: OrderedDict[str, int] = OrderedDict()
    with path.open(newline="", encoding="utf-8") as handle:
        for fields in csv.reader(handle, delimiter="\t"):
            if len(fields) < 4 or fields[0].startswith("N_"):
                continue
            gene_id = re.sub(r"^gene:", "", fields[0])
            gene_id = re.sub(r"\.[0-9]+$", "", gene_id)
            try:
                value = int(float(fields[column]))
            except (TypeError, ValueError):
                value = 0
            values[gene_id] = value
    return values


def write_matrix(path: Path, genes: list[str], samples: list[str], matrix: dict[str, dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(["gene_id", *samples])
        for gene in genes:
            writer.writerow([gene, *[matrix[sample].get(gene, 0) for sample in samples]])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample-table", required=True, type=Path)
    parser.add_argument("--count-column", default="unstranded")
    parser.add_argument("--counts-name", default="counts_matrix.tsv", type=Path)
    parser.add_argument("--abundance-name", default="star_cpm_matrix.tsv", type=Path)
    parser.add_argument("--metadata-name", default="quant_samples.tsv", type=Path)
    args = parser.parse_args()

    column = COUNT_COLUMNS.get(args.count_column)
    if column is None:
        raise ValueError(f"invalid STAR count column: {args.count_column}")
    normalized_column = COUNT_NAMES[column]
    fields, rows = read_table(args.sample_table)
    if not rows:
        raise ValueError("no samples to import")

    genes: list[str] = []
    seen_genes: set[str] = set()
    counts_by_sample: dict[str, dict[str, int]] = {}
    sample_ids: list[str] = []
    for row in rows:
        sample_id = row["import_id"]
        source = Path(row["__source_name"]) / "artifact"
        counts = read_counts(source, column)
        counts_by_sample[sample_id] = counts
        sample_ids.append(sample_id)
        for gene in counts:
            if gene not in seen_genes:
                seen_genes.add(gene)
                genes.append(gene)

    libraries = {sample: sum(counts_by_sample[sample].values()) for sample in sample_ids}
    zero = [sample for sample, total in libraries.items() if total == 0]
    if zero:
        raise ValueError("STAR count libraries with zero total reads: " + ", ".join(zero[:20]))
    cpm_by_sample = {
        sample: {
            gene: counts_by_sample[sample].get(gene, 0) / libraries[sample] * 1_000_000
            for gene in genes
        }
        for sample in sample_ids
    }

    write_matrix(args.counts_name, genes, sample_ids, counts_by_sample)
    write_matrix(args.abundance_name, genes, sample_ids, cpm_by_sample)

    compatibility_fields = [field for field in fields if not field.startswith("__")]
    with args.metadata_name.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=compatibility_fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            row["star_count_column"] = normalized_column
            writer.writerow({field: row.get(field, "") for field in compatibility_fields})

    statistics = {
        "provider": "star",
        "samples": len(sample_ids),
        "genes": len(genes),
        "count_column": normalized_column,
        "library_sizes": libraries,
    }
    Path("import_statistics.json").write_text(
        json.dumps(statistics, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(statistics, sort_keys=True))


if __name__ == "__main__":
    main()
