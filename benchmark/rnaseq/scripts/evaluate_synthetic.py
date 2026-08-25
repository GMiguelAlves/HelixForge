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
    if not truth or len(truth) != len(estimate):
        raise ValueError("numeric metric vectors must be non-empty and equal length")
    logged_truth = [math.log2(value + 1) for value in truth]
    logged_estimate = [math.log2(value + 1) for value in estimate]
    errors = [b - a for a, b in zip(logged_truth, logged_estimate)]
    expressed = [index for index, value in enumerate(truth) if value > 0]
    relative = [abs(estimate[index] - truth[index]) / max(truth[index], 0.1)
                for index in expressed]
    signed_bias = [math.log2((observed + 0.1) / (expected + 0.1))
                   for expected, observed in zip(truth, estimate)]
    return {
        "n": len(truth),
        "spearman": pearson(ranks(truth), ranks(estimate)),
        "spearman_expressed": pearson(
            ranks([truth[index] for index in expressed]),
            ranks([estimate[index] for index in expressed]),
        ) if len(expressed) > 1 else None,
        "pearson_log2_plus_1": pearson(logged_truth, logged_estimate),
        "mae_log2_plus_1": sum(abs(value) for value in errors) / len(errors),
        "rmse_log2_plus_1": math.sqrt(sum(value * value for value in errors) / len(errors)),
        "median_log2_bias": median(errors),
        "median_signed_log2_ratio": median(signed_bias),
        "relative_error_median": median(relative) if relative else None,
        "relative_error_iqr": iqr(relative) if relative else None,
        "expressed": len(expressed),
    }


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("percentile of empty vector")
    position = (len(ordered) - 1) * fraction
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def iqr(values: list[float]) -> float | None:
    return percentile(values, 0.75) - percentile(values, 0.25) if values else None


def signed_metrics(truth: list[float], estimate: list[float]) -> dict[str, float | int | None]:
    if not truth or len(truth) != len(estimate):
        raise ValueError("signed metric vectors must be non-empty and equal length")
    errors = [observed - expected for expected, observed in zip(truth, estimate)]
    return {
        "n": len(truth), "spearman": pearson(ranks(truth), ranks(estimate)),
        "pearson": pearson(truth, estimate),
        "mae": sum(abs(value) for value in errors) / len(errors),
        "rmse": math.sqrt(sum(value * value for value in errors) / len(errors)),
        "median_signed_error": median(errors),
    }


def numeric_or_empty(truth: list[float], estimate: list[float]) -> dict[str, object]:
    return numeric_metrics(truth, estimate) if truth else {"n": 0, "status": "empty_stratum"}


def signed_or_empty(truth: list[float], estimate: list[float]) -> dict[str, object]:
    return signed_metrics(truth, estimate) if truth else {"n": 0, "status": "empty_stratum"}


def wilson_interval(successes: int, total: int, z: float = 1.959963984540054) -> list[float] | None:
    if total == 0:
        return None
    proportion = successes / total
    denominator = 1 + z * z / total
    centre = (proportion + z * z / (2 * total)) / denominator
    half = z * math.sqrt(proportion * (1 - proportion) / total + z * z / (4 * total * total)) / denominator
    return [max(0.0, centre - half), min(1.0, centre + half)]


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


def classification_metrics(labels: list[bool], adjusted: list[float | None],
                           threshold: float = 0.05) -> dict[str, float | int | None]:
    calls = [value is not None and value < threshold for value in adjusted]
    tp = sum(label and call for label, call in zip(labels, calls))
    fp = sum(not label and call for label, call in zip(labels, calls))
    tn = sum(not label and not call for label, call in zip(labels, calls))
    fn = sum(label and not call for label, call in zip(labels, calls))
    return {
        "n": len(labels), "truth_de": sum(labels), "threshold": threshold,
        "called": sum(calls), "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
        "specificity": tn / (tn + fp) if tn + fp else None,
        "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
        "observed_fdp": fp / max(tp + fp, 1),
        "fdp_wilson_95": wilson_interval(fp, tp + fp),
    }


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
        truth_ids = {key for truth_sample, key in transcript_truth if truth_sample == sample}
        keys = sorted(set(observed) & truth_ids)
        missing = sorted(truth_ids - set(observed))
        truth_tpm = [float(transcript_truth[(sample, key)]["tpm"]) for key in keys]
        observed_tpm = [float(observed[key]["TPM"]) for key in keys]
        truth_counts = [float(transcript_truth[(sample, key)]["fragment_count"]) for key in keys]
        observed_counts = [float(observed[key]["NumReads"]) for key in keys]
        transcript_metrics[sample] = {
            "n_total": len(truth_ids), "n_compared": len(keys), "missing_ids": missing,
            "tpm": numeric_metrics(truth_tpm, observed_tpm),
            "fragments": numeric_metrics(truth_counts, observed_counts),
        }

    matrix_samples, observed_gene = matrix(args.case_root / "pipeline/050-quantification/tpm_matrix.tsv")
    if matrix_samples != samples:
        raise ValueError(f"gene matrix sample order differs: {matrix_samples} != {samples}")
    gene_truth = {(row["sample_id"], row["gene_id"]): float(row["tpm"]) for row in gene_truth_rows}
    gene_ids = sorted({row["gene_id"] for row in gene_truth_rows})
    truth_de = {row["gene_id"]: row for row in de_truth_rows}
    observed_gene_ids = set(observed_gene)
    compared_genes = sorted(set(gene_ids) & observed_gene_ids)
    missing_genes = sorted(set(gene_ids) - observed_gene_ids)
    gene_metrics = {}
    for sample in samples:
        expected = [gene_truth[(sample, gene)] for gene in compared_genes]
        estimated = [observed_gene[gene][sample] for gene in compared_genes]
        strata = {}
        for stratum in ("ZERO", "LOW", "MEDIUM", "HIGH"):
            ids = [gene for gene in compared_genes
                   if truth_de[gene]["abundance_stratum"] == stratum]
            strata[stratum] = numeric_or_empty(
                [gene_truth[(sample, gene)] for gene in ids],
                [observed_gene[gene][sample] for gene in ids],
            )
        gene_metrics[sample] = {
            "n_total": len(gene_ids), "n_compared": len(compared_genes),
            "missing_ids": missing_genes,
            "global": numeric_metrics(expected, estimated), "abundance_strata": strata,
        }

    de_rows = table(locate_de(args.case_root))
    observed_de = {row["gene_id"]: row for row in de_rows}
    universe = sorted(set(observed_de) & set(truth_de))
    labels = [truth_de[gene]["is_de"].lower() == "true" for gene in universe]
    adjusted = [finite(observed_de[gene].get("padj")) for gene in universe]
    pvalues = [finite(observed_de[gene].get("pvalue")) for gene in universe]
    finite_pvalues = [value for value in pvalues if value is not None and value > 0]
    floor = min(finite_pvalues) / 10 if finite_pvalues else 1e-300
    scores = [-1.0 if value is None else -math.log10(max(value, floor)) for value in pvalues]
    true_lfc = [float(truth_de[gene]["true_log2fc"]) for gene in universe]
    estimated_lfc = [finite(observed_de[gene].get("log2FoldChange")) or 0.0 for gene in universe]
    direction_genes = [index for index, value in enumerate(true_lfc) if value != 0]
    primary = classification_metrics(labels, adjusted, 0.05)
    effect_strata = {}
    for stratum in ("NONE", "SMALL", "MEDIUM", "LARGE"):
        indices = [index for index, gene in enumerate(universe)
                   if truth_de[gene]["effect_stratum"] == stratum]
        effect_strata[stratum] = {
            "classification": classification_metrics(
                [labels[index] for index in indices],
                [adjusted[index] for index in indices], 0.05,
            ),
            "log2fc": signed_or_empty(
                [true_lfc[index] for index in indices],
                [estimated_lfc[index] for index in indices],
            ),
            "direction_concordance": (
                sum(true_lfc[index] * estimated_lfc[index] > 0 for index in indices
                    if true_lfc[index] != 0)
                / sum(true_lfc[index] != 0 for index in indices)
            ) if any(true_lfc[index] != 0 for index in indices) else None,
        }
    abundance_strata = {}
    for stratum in ("ZERO", "LOW", "MEDIUM", "HIGH"):
        indices = [index for index, gene in enumerate(universe)
                   if truth_de[gene]["abundance_stratum"] == stratum]
        abundance_strata[stratum] = {
            "classification": classification_metrics(
                [labels[index] for index in indices],
                [adjusted[index] for index in indices], 0.05,
            ),
            "log2fc": signed_or_empty(
                [true_lfc[index] for index in indices],
                [estimated_lfc[index] for index in indices],
            ),
        }
    de_metrics = {
        "n_total": len(truth_de), "n_compared": len(universe),
        "missing_ids": sorted(set(truth_de) - set(observed_de)),
        "primary": primary,
        "auroc": auc_roc(labels, scores), "auprc": average_precision(labels, scores),
        "prevalence": sum(labels) / len(labels),
        "log2fc": signed_metrics(true_lfc, estimated_lfc),
        "direction_concordance_de": sum(true_lfc[i] * estimated_lfc[i] > 0 for i in direction_genes) /
                                    len(direction_genes),
        "fdr_calibration": {
            str(threshold): classification_metrics(labels, adjusted, threshold)
            for threshold in (0.01, 0.05, 0.10)
        },
        "effect_strata": effect_strata, "abundance_strata": abundance_strata,
    }

    release_gates = {
        "auroc_above_random": de_metrics["auroc"] is not None and de_metrics["auroc"] > 0.5,
        "auprc_above_prevalence": de_metrics["auprc"] is not None
                                  and de_metrics["auprc"] > de_metrics["prevalence"],
        "positive_log2fc_correlation": de_metrics["log2fc"]["pearson"] is not None
                                       and de_metrics["log2fc"]["pearson"] > 0,
        "all_declared_strata_reported": set(effect_strata) == {"NONE", "SMALL", "MEDIUM", "LARGE"}
                                        and set(abundance_strata) == {"ZERO", "LOW", "MEDIUM", "HIGH"},
    }

    report = {
        "schema_version": "1.0",
        "status": "pass" if all(release_gates.values()) else "fail",
        "samples": samples, "genes_total": len(gene_ids),
        "genes_compared": len(compared_genes), "transcripts_total": 2400,
        "release_gates": release_gates,
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
        writer.writerow({name: primary[name] for name in writer.fieldnames})
    print(json.dumps({"status": report["status"], "samples": len(samples),
                      "genes_compared": len(compared_genes)}))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
