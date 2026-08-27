#!/usr/bin/env python3
"""Evaluate only the biological expectations declared before the GSE52778 run."""

from __future__ import annotations

import argparse
import bisect
import csv
import json
import math
from collections import defaultdict
from pathlib import Path


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def number(value: str | None) -> float | None:
    if value is None or value == "" or value.upper() == "NA":
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expectations", required=True, type=Path)
    parser.add_argument("--gene-catalog", required=True, type=Path)
    parser.add_argument("--expression-long", required=True, type=Path)
    parser.add_argument("--tpm-matrix", required=True, type=Path)
    parser.add_argument("--de-table", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--table-output", required=True, type=Path)
    args = parser.parse_args()

    expectations = [row for row in rows(args.expectations) if row["feature_type"] == "gene"]
    catalog = {row["query"]: row for row in rows(args.gene_catalog)}
    de = {row["gene_id"]: row for row in rows(args.de_table)}
    expression: defaultdict[str, defaultdict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for row in rows(args.expression_long):
        current = number(row.get("TPM"))
        if current is not None:
            expression[row["gene_id"]][row["condition"]].append(current)

    matrix = rows(args.tpm_matrix)
    matrix_fields = [field for field in matrix[0] if field != "gene_id"]
    mean_tpm = {
        row["gene_id"]: sum(float(row[field]) for field in matrix_fields) / len(matrix_fields)
        for row in matrix
    }
    ordered_means = sorted(mean_tpm.values())

    evaluated = []
    for expectation in expectations:
        symbol = expectation["feature"]
        if symbol not in catalog:
            raise ValueError(f"predeclared gene absent from report catalog: {symbol}")
        gene_id = catalog[symbol]["matched_gene_id"]
        if gene_id not in de or gene_id not in mean_tpm:
            raise ValueError(f"predeclared gene absent from DE/TPM artifacts: {symbol}")
        de_row = de[gene_id]
        fold_change = number(de_row.get("log2FoldChange"))
        padj = number(de_row.get("padj"))
        untreated = expression[gene_id].get("untreated", [])
        treated = expression[gene_id].get("dexamethasone", [])
        if len(untreated) != 4 or len(treated) != 4:
            raise ValueError(f"expected four TPM values per condition for {symbol}")
        average = mean_tpm[gene_id]
        percentile = bisect.bisect_right(ordered_means, average) / len(ordered_means)
        expected = expectation["expected_direction"]
        direction_match = fold_change is not None and (
            (expected == "UP" and fold_change > 0) or
            (expected == "DOWN" and fold_change < 0)
        )
        stable_high_heuristic = (
            expected == "STABLE_HIGH" and percentile >= 0.75 and
            fold_change is not None and abs(fold_change) < 1 and
            (padj is None or padj >= 0.05)
        )
        evaluated.append({
            "gene": symbol,
            "gene_id": gene_id,
            "expected_direction": expected,
            "log2_fold_change": fold_change,
            "adjusted_p_value": padj,
            "mean_tpm": average,
            "mean_tpm_untreated": sum(untreated) / len(untreated),
            "mean_tpm_dexamethasone": sum(treated) / len(treated),
            "expression_percentile": percentile,
            "direction_match": direction_match if expected in {"UP", "DOWN"} else None,
            "significant_at_0_05": padj is not None and padj < 0.05,
            "stable_high_descriptive_heuristic": stable_high_heuristic,
            "evidence_type": expectation["evidence_type"],
            "source": expectation["source"],
        })

    responsive = [row for row in evaluated if row["expected_direction"] in {"UP", "DOWN"}]
    controls = [row for row in evaluated if row["expected_direction"] == "STABLE_HIGH"]
    sanity_pass = len(responsive) == 5 and all(row["direction_match"] for row in responsive)
    document = {
        "schema_version": "1.0",
        "status": "SANITY_CHECK_PASS" if sanity_pass else "SANITY_CHECK_DEVIATION",
        "dataset": "GSE52778",
        "release_gate": False,
        "responsive_genes": len(responsive),
        "responsive_direction_matches": sum(bool(row["direction_match"]) for row in responsive),
        "responsive_significant_at_0_05": sum(row["significant_at_0_05"] for row in responsive),
        "reference_controls": len(controls),
        "reference_controls_matching_descriptive_heuristic": sum(
            row["stable_high_descriptive_heuristic"] for row in controls
        ),
        "stable_high_heuristic": (
            "mean TPM percentile >= 0.75, abs(log2FC) < 1 and padj >= 0.05/NA; "
            "descriptive only and not preregistered as a release gate"
        ),
        "genes": evaluated,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.table_output.parent.mkdir(parents=True, exist_ok=True)
    with args.table_output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(evaluated[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(evaluated)
    print(json.dumps({"status": document["status"], "genes": len(evaluated)}))
    return 0 if sanity_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
