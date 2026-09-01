#!/usr/bin/env python3
"""Compare two 10B executions without treating volatile metadata as science."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


SCIENTIFIC_TSV = {
    "entity_map.tsv", "contrast_map.tsv", "mark_map.tsv", "master_evidence.tsv",
    "master_evidence_long.tsv", "peak_aggregation.tsv", "regulatory_classes.tsv",
    "candidate_score.tsv", "candidate_ranking.tsv", "fisher_tests.tsv", "correlations.tsv",
    "functional_gene_sets.tsv", "functional_tests.tsv",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes())
    return digest.hexdigest()


def canonical_tsv(path: Path) -> tuple[tuple[str, ...], tuple[tuple[str, ...], ...]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        rows = list(reader)
    return tuple(rows[0]), tuple(sorted(tuple(row) for row in rows[1:]))


def locate(root: Path, name: str) -> Path:
    candidates = [path for path in root.rglob(name) if path.is_file()]
    if not candidates:
        raise FileNotFoundError(f"missing deterministic table {name}")
    semantic = {canonical_tsv(path) for path in candidates}
    if len(semantic) != 1:
        raise ValueError(f"non-identical duplicate tables within run: {name}")
    return sorted(candidates, key=lambda path: (len(path.parts), path.as_posix()))[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-a", type=Path, required=True)
    parser.add_argument("--run-b", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = []
    for name in sorted(SCIENTIFIC_TSV):
        try:
            left, right = locate(args.run_a, name), locate(args.run_b, name)
        except FileNotFoundError:
            continue
        semantic = canonical_tsv(left) == canonical_tsv(right)
        rows.append({"artifact": name, "semantic_identity": semantic, "byte_identity": sha256(left) == sha256(right), "run_a_sha256": sha256(left), "run_b_sha256": sha256(right)})
    manifests = [path for path in args.run_a.rglob("integrative_run_manifest.json") if path.is_file()]
    reports = [path for path in args.run_a.rglob("integrative_report.html") if path.is_file()]
    result = {
        "schema_version": "1.0", "type": "integrative_synthetic_determinism",
        "run_a": str(args.run_a.resolve()), "run_b": str(args.run_b.resolve()),
        "tables_compared": len(rows), "semantic_identity": bool(rows) and all(row["semantic_identity"] for row in rows),
        "byte_identity_required_tables": all(row["byte_identity"] for row in rows),
        "volatile_json_compared_by_schema_and_scientific_tables": bool(manifests),
        "html_excluded_from_byte_identity": bool(reports), "artifacts": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"semantic_identity": result["semantic_identity"], "tables_compared": len(rows)}, sort_keys=True))
    if not result["semantic_identity"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
