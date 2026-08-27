#!/usr/bin/env python3
"""Compute the preregistered GSE52778 concordance metrics."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


def metrics(left: pd.Series, right: pd.Series) -> dict[str, object]:
    left = pd.to_numeric(left, errors="coerce")
    right = pd.to_numeric(right, errors="coerce")
    valid = np.isfinite(left.to_numpy()) & np.isfinite(right.to_numpy())
    observed = left.to_numpy()[valid]
    reference = right.to_numpy()[valid]
    delta = observed - reference
    if len(observed) < 2:
        pearson = spearman = None
    else:
        pearson = float(np.corrcoef(observed, reference)[0, 1])
        spearman = float(
            pd.Series(observed).rank(method="average").corr(
                pd.Series(reference).rank(method="average")
            )
        )
    return {
        "n_total": int(len(left)),
        "n_compared": int(valid.sum()),
        "n_excluded": int(len(left) - valid.sum()),
        "pearson": pearson,
        "spearman": spearman,
        "mae": float(np.mean(np.abs(delta))) if len(delta) else None,
        "rmse": float(math.sqrt(np.mean(delta ** 2))) if len(delta) else None,
        "maximum_absolute_delta": float(np.max(np.abs(delta))) if len(delta) else None,
    }


def set_metrics(left: set[str], right: set[str]) -> dict[str, object]:
    intersection = left & right
    union = left | right
    return {
        "helixforge": len(left),
        "independent": len(right),
        "intersection": len(intersection),
        "union": len(union),
        "jaccard": len(intersection) / len(union) if union else 1.0,
        "overlap_coefficient": (
            len(intersection) / min(len(left), len(right))
            if left and right else (1.0 if not union else 0.0)
        ),
    }


def write_table(path: Path, records: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame.from_records(records).to_csv(path, sep="\t", index=False)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-root", required=True, type=Path)
    parser.add_argument("--reference-root", required=True, type=Path)
    parser.add_argument("--sample-table", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    sample_table = pd.read_csv(args.sample_table, sep="\t", dtype=str)
    samples = sample_table["sample_id"].tolist()
    if len(samples) != 8 or len(set(samples)) != 8:
        raise ValueError("expected eight unique samples")

    quantification: list[dict[str, object]] = []
    for sample in samples:
        left_path = args.case_root / f"pipeline/040-alignment/quants/gse52778_airway/{sample}/quant.sf"
        right_path = args.reference_root / f"quant/{sample}/quant.sf"
        columns = ["Name", "EffectiveLength", "TPM", "NumReads"]
        left = pd.read_csv(left_path, sep="\t", usecols=columns)
        right = pd.read_csv(right_path, sep="\t", usecols=columns)
        if not left["Name"].equals(right["Name"]):
            raise ValueError(f"transcript identity/order differs for {sample}")
        for field in columns[1:]:
            quantification.append({
                "level": "transcript", "artifact": "quant.sf", "sample_id": sample,
                "field": field, **metrics(left[field], right[field]),
            })

    for filename, field_name in (
        ("counts_matrix.tsv", "counts"),
        ("tpm_matrix.tsv", "TPM"),
        ("length_matrix.tsv", "length"),
    ):
        left = pd.read_csv(args.case_root / f"pipeline/050-quantification/{filename}", sep="\t")
        right = pd.read_csv(args.reference_root / f"analysis/{filename}", sep="\t")
        if not left["gene_id"].equals(right["gene_id"]):
            raise ValueError(f"gene identity/order differs for {filename}")
        for sample in samples:
            left_column = f"gse52778_airway__{sample}"
            quantification.append({
                "level": "gene", "artifact": filename, "sample_id": sample,
                "field": field_name, **metrics(left[left_column], right[sample]),
            })
    write_table(args.output_dir / "quantification_concordance.tsv", quantification)

    helix_path = args.case_root / "pipeline/060-deg-analysis/benchmark_airway_primary/differential_expression_results.tsv"
    reference_path = args.reference_root / "analysis/de_results.tsv"
    helix = pd.read_csv(helix_path, sep="\t")
    reference = pd.read_csv(reference_path, sep="\t")
    merged = helix.merge(reference, on="gene_id", suffixes=("_helixforge", "_independent"),
                         validate="one_to_one")
    if len(merged) != len(helix) or len(merged) != len(reference):
        raise ValueError("DE gene universes differ")

    de_records = []
    for left_field, right_field, label in (
        ("baseMean_helixforge", "baseMean_independent", "baseMean"),
        ("log2FoldChange_helixforge", "log2FoldChange_independent", "log2FoldChange"),
        ("lfcSE_helixforge", "lfcSE_independent", "lfcSE"),
        ("statistic", "stat", "Wald_statistic"),
    ):
        de_records.append({"field": label, "transformation": "none",
                           **metrics(merged[left_field], merged[right_field])})
    for field in ("pvalue", "padj"):
        left = pd.to_numeric(merged[f"{field}_helixforge"], errors="coerce")
        right = pd.to_numeric(merged[f"{field}_independent"], errors="coerce")
        left_transformed = -np.log10(left.clip(lower=1e-300))
        right_transformed = -np.log10(right.clip(lower=1e-300))
        de_records.append({
            "field": field,
            "transformation": "-log10; pairwise NA excluded; zero capped at 1e-300",
            "helixforge_na": int(left.isna().sum()),
            "independent_na": int(right.isna().sum()),
            "helixforge_zero": int((left == 0).sum()),
            "independent_zero": int((right == 0).sum()),
            **metrics(left_transformed, right_transformed),
        })
    finite_effect = (
        np.isfinite(pd.to_numeric(merged["log2FoldChange_helixforge"], errors="coerce")) &
        np.isfinite(pd.to_numeric(merged["log2FoldChange_independent"], errors="coerce"))
    )
    effects_left = merged.loc[finite_effect, "log2FoldChange_helixforge"]
    effects_right = merged.loc[finite_effect, "log2FoldChange_independent"]
    nonzero = (effects_left != 0) & (effects_right != 0)
    direction_concordance = float(
        (np.sign(effects_left[nonzero]) == np.sign(effects_right[nonzero])).mean()
    )
    for record in de_records:
        if record["field"] == "log2FoldChange":
            record["direction_concordance"] = direction_concordance
    write_table(args.output_dir / "de_concordance.tsv", de_records)

    left_padj = pd.to_numeric(merged["padj_helixforge"], errors="coerce")
    right_padj = pd.to_numeric(merged["padj_independent"], errors="coerce")
    left_lfc = pd.to_numeric(merged["log2FoldChange_helixforge"], errors="coerce")
    right_lfc = pd.to_numeric(merged["log2FoldChange_independent"], errors="coerce")
    identities = merged["gene_id"]
    deg_records = []
    masks = {
        "all": (left_padj < 0.05, right_padj < 0.05),
        "up": ((left_padj < 0.05) & (left_lfc > 0), (right_padj < 0.05) & (right_lfc > 0)),
        "down": ((left_padj < 0.05) & (left_lfc < 0), (right_padj < 0.05) & (right_lfc < 0)),
        "effect_filtered": (
            (left_padj < 0.05) & (left_lfc.abs() >= 1),
            (right_padj < 0.05) & (right_lfc.abs() >= 1),
        ),
    }
    for category, (left_mask, right_mask) in masks.items():
        deg_records.append({
            "category": category, "padj_threshold": 0.05,
            "absolute_log2fc_threshold": 1 if category == "effect_filtered" else None,
            **set_metrics(set(identities[left_mask]), set(identities[right_mask])),
        })
    write_table(args.output_dir / "deg_overlap.tsv", deg_records)

    ranking_records = []
    ranking_values = {
        "padj": (left_padj.fillna(1.0), right_padj.fillna(1.0), True),
        "absolute_log2FoldChange": (left_lfc.abs().fillna(-np.inf), right_lfc.abs().fillna(-np.inf), False),
        "signed_log2FoldChange": (left_lfc.fillna(-np.inf), right_lfc.fillna(-np.inf), False),
    }
    for label, (left_values, right_values, ascending) in ranking_values.items():
        left_ranks = left_values.rank(method="average", ascending=ascending)
        right_ranks = right_values.rank(method="average", ascending=ascending)
        spearman = float(left_ranks.corr(right_ranks))
        for requested in (25, 50, 100, 250):
            left_order = identities.iloc[np.argsort(left_values.to_numpy(), kind="stable")]
            right_order = identities.iloc[np.argsort(right_values.to_numpy(), kind="stable")]
            if not ascending:
                left_order = left_order.iloc[::-1]
                right_order = right_order.iloc[::-1]
            overlap = len(set(left_order.iloc[:requested]) & set(right_order.iloc[:requested]))
            ranking_records.append({
                "ranking": label, "spearman": spearman, "top_n": requested,
                "shared": overlap, "overlap_fraction": overlap / requested,
                "na_policy": "padj NA=1; effect NA ranked last",
            })
    write_table(args.output_dir / "ranking_concordance.tsv", ranking_records)

    summary = {
        "schema_version": "1.0", "status": "complete", "dataset": "GSE52778",
        "comparison": "METHOD_CONTROLLED", "samples": samples,
        "quantification_records": len(quantification),
        "de_gene_universe": len(merged),
        "log2fc_direction_concordance": direction_concordance,
        "deg_overlap": deg_records,
        "pvalue_policy": "-log10; pairwise NA excluded; zeros capped at 1e-300",
        "outputs": ["quantification_concordance.tsv", "de_concordance.tsv",
                    "deg_overlap.tsv", "ranking_concordance.tsv"],
    }
    (args.output_dir / "concordance_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": "complete", "records": len(quantification) + len(de_records)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
