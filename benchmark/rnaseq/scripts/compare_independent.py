#!/usr/bin/env python3
"""Semantic comparison of HelixForge and the independent same-method harness."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def value(text: str | None) -> float | None:
    if text is None or text == "" or text.upper() == "NA":
        return None
    result = float(text)
    return result if math.isfinite(result) else None


def equal(observed: float | None, reference: float | None) -> tuple[bool, float | None]:
    if observed is None or reference is None:
        return observed is None and reference is None, None
    delta = abs(observed - reference)
    return delta <= 1e-8 + 1e-6 * abs(reference), delta


def compare(path_a: Path, path_b: Path, key: str,
            fields: list[tuple[str, str]]) -> dict[str, object]:
    left_rows, right_rows = rows(path_a), rows(path_b)
    left_order = [row[key] for row in left_rows]
    right_order = [row[key] for row in right_rows]
    if left_order != right_order:
        raise ValueError(f"row identity/order differs: {path_a} versus {path_b}")
    mismatches: list[dict[str, object]] = []
    mismatch_count = 0
    max_delta = 0.0
    for left, right in zip(left_rows, right_rows):
        for left_field, right_field in fields:
            matches, delta = equal(value(left.get(left_field)), value(right.get(right_field)))
            if delta is not None:
                max_delta = max(max_delta, delta)
            if not matches and len(mismatches) < 100:
                mismatches.append({"id": left[key], "field": left_field,
                                   "observed": left.get(left_field), "reference": right.get(right_field)})
            if not matches:
                mismatch_count += 1
    return {"rows": len(left_rows), "mismatch_count": mismatch_count,
            "mismatches_capped_at": 100, "maximum_absolute_delta": max_delta,
            "status": "pass" if mismatch_count == 0 else "fail", "examples": mismatches}


def matrix_fields(path: Path) -> list[str]:
    with path.open(encoding="utf-8", newline="") as handle:
        header = next(csv.reader(handle, delimiter="\t"))
    return [field for field in header if field != "gene_id"]


def helix_de(case_root: Path) -> Path:
    preferred = case_root / "pipeline/060-deg-analysis/native/differential_expression_results.tsv"
    candidates = [preferred] if preferred.is_file() else list(
        (case_root / "pipeline/060-deg-analysis").rglob("differential_expression_results.tsv")
    )
    if len(candidates) != 1:
        raise ValueError(f"expected one HelixForge DE table, found {len(candidates)}")
    return candidates[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-root", required=True, type=Path)
    parser.add_argument("--reference-root", required=True, type=Path)
    parser.add_argument("--sample-table", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    samples = [row["sample_id"] for row in rows(args.sample_table)]
    comparisons: dict[str, object] = {}
    for sample in samples:
        comparisons[f"quant/{sample}"] = compare(
            args.case_root / f"pipeline/040-alignment/quants/POLYESTER_V1/{sample}/quant.sf",
            args.reference_root / f"quant/{sample}/quant.sf", "Name",
            [(field, field) for field in ("Length", "EffectiveLength", "TPM", "NumReads")],
        )
    for filename in ("counts_matrix.tsv", "tpm_matrix.tsv", "length_matrix.tsv"):
        left = args.case_root / f"pipeline/050-quantification/{filename}"
        right = args.reference_root / f"analysis/{filename}"
        left_fields = matrix_fields(left)
        right_fields = matrix_fields(right)
        normalized_left = [field.split("__", 1)[-1] for field in left_fields]
        if normalized_left != right_fields or normalized_left != samples:
            raise ValueError(f"matrix sample order differs for {filename}")
        comparisons[f"import/{filename}"] = compare(
            left, right, "gene_id", list(zip(left_fields, right_fields))
        )
    comparisons["differential_expression"] = compare(
        helix_de(args.case_root), args.reference_root / "analysis/de_results.tsv", "gene_id",
        [("baseMean", "baseMean"), ("log2FoldChange", "log2FoldChange"),
         ("lfcSE", "lfcSE"), ("statistic", "stat"), ("pvalue", "pvalue"), ("padj", "padj")],
    )
    status = "pass" if all(item["status"] == "pass" for item in comparisons.values()) else "fail"
    document = {"schema_version": "1.0", "status": status, "tolerance": "1e-8 + 1e-6*abs(reference)",
                "samples": samples, "comparisons": comparisons}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "comparisons": len(comparisons)}))
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
