#!/usr/bin/env python3
"""Semantic assertions for the reduced real RNA-seq gene report."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: validate_real_report.py RESULTS_DIR")
    root = Path(sys.argv[1])
    required_tables = {
        "gene_catalog.tsv",
        "expression_long.tsv",
        "expression_summary_by_context.tsv",
        "deg_hits.tsv",
        "gene_expression_summary.tsv",
    }
    actual_tables = {path.name for path in (root / "tables").glob("*.tsv")}
    if not required_tables.issubset(actual_tables):
        raise ValueError(f"Missing report tables: {sorted(required_tables - actual_tables)}")

    catalog = rows(root / "tables/gene_catalog.tsv")
    expression = rows(root / "tables/expression_long.tsv")
    deg_hits = rows(root / "tables/deg_hits.tsv")
    if {row["matched_gene_id"] for row in catalog} != {"gene_alpha", "gene_beta"}:
        raise ValueError("Candidate-gene catalog does not preserve both fixture genes.")
    if len(expression) != 8:
        raise ValueError(f"Expected 2 genes x 4 samples, observed {len(expression)} rows.")
    if {row["gene_id"] for row in deg_hits} != {"gene_alpha", "gene_beta"}:
        raise ValueError("DE results were not joined to both candidate genes.")

    html = (root / "gene_set_report.html").read_text(encoding="utf-8")
    if "Stub candidate gene report" not in html or "gene_alpha" not in html or "gene_beta" not in html:
        raise ValueError("Rendered HTML is missing its title or candidate genes.")
    plots = [path for path in (root / "plots").glob("*.png") if path.stat().st_size > 100]
    if not plots:
        raise ValueError("No non-empty scientific PNG was generated.")

    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("status") != "complete" or manifest.get("provider") != "candidate_genes_v1":
        raise ValueError("Final manifest does not certify the real provider execution.")
    if manifest.get("sample_count") != 4 or manifest.get("query_count") != 2:
        raise ValueError("Final manifest contains incorrect fixture dimensions.")
    session = (root / "sessionInfo.txt").read_text(encoding="utf-8")
    if "R version 4.3.3" not in session:
        raise ValueError("Pinned R 4.3.3 is not recorded in sessionInfo.txt.")
    print(json.dumps({"tables": len(actual_tables), "plots": len(plots), "samples": 4, "queries": 2}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
