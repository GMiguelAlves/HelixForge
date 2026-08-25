#!/usr/bin/env python3
"""Evaluate HelixForge RNA-seq abundance and DE against frozen synthetic truth."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from statistics import median


def table(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def finite(value: str | None) -> float | None:
    if value is None or value == "" or value.upper() == "NA":
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=values.__getitem__)
    result = [0.0] * len(values)
    cursor = 0
    while cursor < len(order):
        end = cursor + 1
        while end < len(order) and values[order[end]] == values[order[cursor]]:
            end += 1
        rank = (cursor + 1 + end) / 2
        for index in order[cursor:end]:
            result[index] = rank
        cursor = end
    return result


def pearson(left: list[float], right: list[float]) -> float | None:
    if len(left) < 2:
        return None
    mean_left, mean_right = sum(left) / len(left), sum(right) / len(right)
    numerator = sum((a - mean_left) * (b - mean_right) for a, b in zip(left, right))
    denominator = math.sqrt(sum((a - mean_left) ** 2 for a in left) *
                            sum((b - mean_right) ** 2 for b in right))
    return numerator / denominator if denominator else None


def numeric_metrics(truth: list[float], estimate: list[float]) -> dict[str, float | int | None]:
    logged_truth = [math.log2(value + 1) for value in truth]
    logged_estimate = [math.log2(value + 1) for value in estimate]
    errors = [b - a for a, b in zip(logged_truth, logged_estimate)]
    return {
        "n": len(truth),
        "spearman": pearson(ranks(truth), ranks(estimate)),
        "pearson_log2_plus_1": pearson(logged_truth, logged_estimate),
        "mae_log2_plus_1": sum(abs(value) for value in errors) / len(errors),
        "rmse_log2_plus_1": math.sqrt(sum(value * value for value in errors) / len(errors)),
        "median_log2_bias": median(errors),
    }


def matrix(path: Path) -> tuple[list[str], dict[str, dict[str, float]]]:
    rows = table(path)
    if not rows or "gene_id" not in rows[0]:
        raise ValueError(f"invalid matrix: {path}")
    columns = [name for name in rows[0] if name != "gene_id"]
    values = {row["gene_id"]: {name.split("__", 1)[-1]: float(row[name]) for name in columns}
              for row in rows}
    return [name.split("__", 1)[-1] for name in columns], values


def auc_roc(labels: list[bool], scores: list[float]) -> float | None:
    positive = sum(labels)
    negative = len(labels) - positive
    if not positive or not negative:
        return None
    ranked = ranks(scores)
    positive_rank_sum = sum(rank for rank, label in zip(ranked, labels) if label)
    return (positive_rank_sum - positive * (positive + 1) / 2) / (positive * negative)


def average_precision(labels: list[bool], scores: list[float]) -> float | None:
    positive = sum(labels)
    if not positive:
        return None
    ordered = sorted(zip(scores, labels), reverse=True)
    true_positive = 0
    total = 0
    area = 0.0
    for _, label in ordered:
        total += 1
        if label:
            true_positive += 1
            area += true_positive / total
    return area / positive


def locate_de(case_root: Path) -> Path:
    preferred = case_root / "pipeline/060-deg-analysis/native/differential_expression_results.tsv"
    if preferred.is_file():
        return preferred
    candidates = list((case_root / "pipeline/060-deg-analysis").rglob("differential_expression_results.tsv"))
    if len(candidates) != 1:
        raise ValueError(f"expected one aggregate DE table, found {len(candidates)}")
    return candidates[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--truth-dir", required=True, type=Path)
    parser.add_argument("--case-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise FileExistsError(args.output_dir)
    args.output_dir.mkdir(parents=True)

    sample_rows = table(args.truth_dir / "sample_table.tsv")
    samples = [row["sample_id"] for row in sample_rows]
    transcript_truth_rows = table(args.truth_dir / "transcript_truth.tsv")
    gene_truth_rows = table(args.truth_dir / "gene_truth.tsv")
    de_truth_rows = table(args.truth_dir / "gene_de_truth.tsv")

    transcript_truth = {(row["sample_id"], row["transcript_id"]): row for row in transcript_truth_rows}
    transcript_metrics: dict[str, object] = {}
    for sample in samples:
        quant = args.case_root / f"pipeline/040-alignment/quants/POLYESTER_V1/{sample}/quant.sf"
        observed = {row["Name"]: row for row in table(quant)}
        keys = sorted(key for key in observed if (sample, key) in transcript_truth)
        if len(keys) != 2400:
            raise ValueError(f"{sample}: compared {len(keys)} transcripts, expected 2400")
        truth_tpm = [float(transcript_truth[(sample, key)]["tpm"]) for key in keys]
        observed_tpm = [float(observed[key]["TPM"]) for key in keys]
        truth_counts = [float(transcript_truth[(sample, key)]["fragment_count"]) for key in keys]
        observed_counts = [float(observed[key]["NumReads"]) for key in keys]
        transcript_metrics[sample] = {
            "tpm": numeric_metrics(truth_tpm, observed_tpm),
            "fragments": numeric_metrics(truth_counts, observed_counts),
        }

    matrix_samples, observed_gene = matrix(args.case_root / "pipeline/050-quantification/tpm_matrix.tsv")
    if matrix_samples != samples:
        raise ValueError(f"gene matrix sample order differs: {matrix_samples} != {samples}")
    gene_truth = {(row["sample_id"], row["gene_id"]): float(row["tpm"]) for row in gene_truth_rows}
    gene_ids = sorted({row["gene_id"] for row in gene_truth_rows})
    gene_metrics = {}
    for sample in samples:
        gene_metrics[sample] = numeric_metrics(
            [gene_truth[(sample, gene)] for gene in gene_ids],
            [observed_gene[gene][sample] for gene in gene_ids],
        )

    de_rows = table(locate_de(args.case_root))
    observed_de = {row["gene_id"]: row for row in de_rows}
    truth_de = {row["gene_id"]: row for row in de_truth_rows}
    universe = sorted(set(observed_de) & set(truth_de))
    if len(universe) != 1200:
        raise ValueError(f"DE universe has {len(universe)} genes, expected 1200")
    labels = [truth_de[gene]["is_de"].lower() == "true" for gene in universe]
    adjusted = [finite(observed_de[gene].get("padj")) for gene in universe]
    calls = [value is not None and value < 0.05 for value in adjusted]
    tp = sum(label and call for label, call in zip(labels, calls))
    fp = sum(not label and call for label, call in zip(labels, calls))
    tn = sum(not label and not call for label, call in zip(labels, calls))
    fn = sum(label and not call for label, call in zip(labels, calls))
    pvalues = [finite(observed_de[gene].get("pvalue")) for gene in universe]
    finite_pvalues = [value for value in pvalues if value is not None and value > 0]
    floor = min(finite_pvalues) / 10 if finite_pvalues else 1e-300
    scores = [-1.0 if value is None else -math.log10(max(value, floor)) for value in pvalues]
    true_lfc = [float(truth_de[gene]["true_log2fc"]) for gene in universe]
    estimated_lfc = [finite(observed_de[gene].get("log2FoldChange")) or 0.0 for gene in universe]
    direction_genes = [index for index, value in enumerate(true_lfc) if value != 0]
    de_metrics = {
        "universe": len(universe), "truth_de": sum(labels), "called": sum(calls),
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
        "specificity": tn / (tn + fp) if tn + fp else None,
        "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
        "observed_fdp": fp / max(tp + fp, 1),
        "auroc": auc_roc(labels, scores), "auprc": average_precision(labels, scores),
        "prevalence": sum(labels) / len(labels),
        "log2fc": numeric_metrics(true_lfc, estimated_lfc),
        "direction_concordance_de": sum(true_lfc[i] * estimated_lfc[i] > 0 for i in direction_genes) /
                                    len(direction_genes),
    }

    report = {
        "schema_version": "1.0", "status": "complete",
        "samples": samples, "genes": len(gene_ids), "transcripts": 2400,
        "transcript": transcript_metrics, "gene": gene_metrics, "differential_expression": de_metrics,
    }
    (args.output_dir / "synthetic_metrics.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    with (args.output_dir / "de_confusion.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["tp", "fp", "tn", "fn", "precision", "recall",
                                                        "specificity", "f1", "observed_fdp"],
                                delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerow({name: de_metrics[name] for name in writer.fieldnames})
    print(json.dumps({"status": "complete", "samples": len(samples), "genes": len(gene_ids)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
