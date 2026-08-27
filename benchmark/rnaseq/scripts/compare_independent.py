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
            fields: list[tuple[str, str]], order_required: bool = True) -> dict[str, object]:
    left_rows, right_rows = rows(path_a), rows(path_b)
    left_order = [row[key] for row in left_rows]
    right_order = [row[key] for row in right_rows]
    if len(left_order) != len(set(left_order)) or len(right_order) != len(set(right_order)):
        raise ValueError(f"duplicate row identity: {path_a} versus {path_b}")
    if set(left_order) != set(right_order):
        raise ValueError(f"row identity set differs: {path_a} versus {path_b}")
    same_order = left_order == right_order
    if order_required and not same_order:
        raise ValueError(f"row identity/order differs: {path_a} versus {path_b}")
    if not same_order:
        right_by_id = {row[key]: row for row in right_rows}
        right_rows = [right_by_id[identity] for identity in left_order]
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
    return {"rows": len(left_rows), "same_row_order": same_order,
            "row_order_required": order_required, "mismatch_count": mismatch_count,
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


def rank_values(values: dict[str, float]) -> dict[str, float]:
    ordered = sorted(values, key=lambda identity: (values[identity], identity))
    result: dict[str, float] = {}
    cursor = 0
    while cursor < len(ordered):
        end = cursor + 1
        while end < len(ordered) and values[ordered[end]] == values[ordered[cursor]]:
            end += 1
        rank = (cursor + 1 + end) / 2
        for identity in ordered[cursor:end]:
            result[identity] = rank
        cursor = end
    return result


def pearson(left: list[float], right: list[float]) -> float | None:
    if len(left) < 2:
        return None
    left_mean, right_mean = sum(left) / len(left), sum(right) / len(right)
    numerator = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right))
    denominator = math.sqrt(sum((a - left_mean) ** 2 for a in left)
                            * sum((b - right_mean) ** 2 for b in right))
    return numerator / denominator if denominator else None


def de_sets_and_rankings(path_a: Path, path_b: Path) -> dict[str, object]:
    left = {row["gene_id"]: row for row in rows(path_a)}
    right = {row["gene_id"]: row for row in rows(path_b)}
    if set(left) != set(right):
        raise ValueError("DE gene universes differ")
    significant = []
    for dataset in (left, right):
        significant.append({gene for gene, row in dataset.items()
                            if value(row.get("padj")) is not None and value(row.get("padj")) < 0.05})
    intersection = significant[0] & significant[1]
    union = significant[0] | significant[1]
    direction_ids = sorted(intersection)
    direction = sum(
        (value(left[gene].get("log2FoldChange")) or 0.0)
        * (value(right[gene].get("log2FoldChange")) or 0.0) > 0
        for gene in direction_ids
    ) / len(direction_ids) if direction_ids else None
    pvalue_left = {gene: value(row.get("pvalue")) if value(row.get("pvalue")) is not None else 1.0
                   for gene, row in left.items()}
    pvalue_right = {gene: value(row.get("pvalue")) if value(row.get("pvalue")) is not None else 1.0
                    for gene, row in right.items()}
    ranks_left, ranks_right = rank_values(pvalue_left), rank_values(pvalue_right)
    genes = sorted(left)
    top_overlap = {}
    ordered_left = sorted(genes, key=lambda gene: (pvalue_left[gene], gene))
    ordered_right = sorted(genes, key=lambda gene: (pvalue_right[gene], gene))
    for requested in (50, 100, 250, 500):
        count = min(requested, len(genes))
        shared = len(set(ordered_left[:count]) & set(ordered_right[:count]))
        top_overlap[str(requested)] = {"evaluated_n": count, "shared": shared,
                                       "fraction": shared / count if count else None}
    return {
        "left_significant": len(significant[0]), "right_significant": len(significant[1]),
        "intersection": len(intersection), "union": len(union),
        "jaccard": len(intersection) / len(union) if union else 1.0,
        "overlap_coefficient": len(intersection) / min(map(len, significant))
                               if all(significant) else (1.0 if not union else 0.0),
        "direction_concordance_common_significant": direction,
        "pvalue_rank_spearman": pearson(
            [ranks_left[gene] for gene in genes], [ranks_right[gene] for gene in genes]
        ),
        "top_n_overlap": top_overlap,
    }


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
    helix_de_path = helix_de(args.case_root)
    reference_de_path = args.reference_root / "analysis/de_results.tsv"
    comparisons["differential_expression"] = compare(
        helix_de_path, reference_de_path, "gene_id",
        [("baseMean", "baseMean"), ("log2FoldChange", "log2FoldChange"),
         ("lfcSE", "lfcSE"), ("statistic", "stat"), ("pvalue", "pvalue"), ("padj", "padj")],
        order_required=False,
    )
    comparisons["de_sets_and_rankings"] = de_sets_and_rankings(helix_de_path, reference_de_path)
    status = "pass" if all(item.get("status", "pass") == "pass"
                           for item in comparisons.values()) else "fail"
    document = {"schema_version": "1.0", "status": status, "tolerance": "1e-8 + 1e-6*abs(reference)",
                "samples": samples, "comparisons": comparisons}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "comparisons": len(comparisons)}))
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
