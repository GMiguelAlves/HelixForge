#!/usr/bin/env python3
"""Prepare compact plotting tables from frozen Polyester benchmark evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_tsv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def as_float(value: str | None) -> float | None:
    if value is None or value.strip().upper() in {"", "NA", "NAN"}:
        return None
    return float(value)


def abundance_stratum(value: float) -> str:
    if value == 0:
        return "ZERO"
    if value < 1:
        return "LOW"
    if value < 10:
        return "MEDIUM"
    return "HIGH"


def stable_jitter(identifier: str) -> float:
    value = int.from_bytes(hashlib.sha256(identifier.encode()).digest()[:2], "big")
    return ((value / 65535.0) - 0.5) * 0.08


def comparison_row(label: str, path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    metrics = data["comparisons"]["de_sets_and_rankings"]
    return {
        "arm": label,
        "strict_numeric_status": data["status"],
        "deg_jaccard": metrics["jaccard"],
        "direction_concordance": metrics["direction_concordance_common_significant"],
        "pvalue_rank_spearman": metrics["pvalue_rank_spearman"],
        "top100_overlap": metrics["top_n_overlap"]["100"]["fraction"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--truth-dir", required=True, type=Path)
    parser.add_argument("--tpm-matrix", required=True, type=Path)
    parser.add_argument("--de-results", required=True, type=Path)
    parser.add_argument("--metrics", required=True, type=Path)
    parser.add_argument("--performance", required=True, type=Path)
    parser.add_argument("--clean-comparison", required=True, type=Path)
    parser.add_argument("--independent-comparison", required=True, type=Path)
    parser.add_argument("--reference-repeat-comparison", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    if not os.environ.get("SLURM_JOB_ID"):
        raise SystemExit("figure preparation must execute inside a Slurm job")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    truth_rows = read_tsv(args.truth_dir / "gene_truth.tsv")
    truth = {(r["gene_id"], r["sample_id"]): r for r in truth_rows}
    matrix_rows = read_tsv(args.tpm_matrix)
    matrix_columns = [k for k in matrix_rows[0] if k != "gene_id"]
    sample_columns = {column: column.split("__", 1)[-1] for column in matrix_columns}
    abundance_rows = []
    for estimate in matrix_rows:
        for column, sample in sample_columns.items():
            key = (estimate["gene_id"], sample)
            if key not in truth:
                continue
            true_tpm = float(truth[key]["tpm"])
            abundance_rows.append({
                "gene_id": estimate["gene_id"],
                "sample_id": sample,
                "condition": truth[key]["condition"],
                "true_tpm": true_tpm,
                "estimated_tpm": float(estimate[column]),
                "abundance_stratum": abundance_stratum(true_tpm),
            })
    write_tsv(
        args.output_dir / "gene_abundance.tsv",
        abundance_rows,
        ["gene_id", "sample_id", "condition", "true_tpm", "estimated_tpm", "abundance_stratum"],
    )

    metrics = json.loads(args.metrics.read_text(encoding="utf-8"))
    transcript_rows = []
    for sample, values in metrics["transcript"].items():
        transcript_rows.append({
            "sample_id": sample,
            "n_transcripts": values["n_compared"],
            "tpm_spearman": values["tpm"]["spearman"],
            "tpm_pearson_log2": values["tpm"]["pearson_log2_plus_1"],
            "tpm_mae_log2": values["tpm"]["mae_log2_plus_1"],
            "fragment_spearman": values["fragments"]["spearman"],
        })
    transcript_rows.sort(key=lambda row: row["sample_id"])
    write_tsv(
        args.output_dir / "transcript_metrics.tsv",
        transcript_rows,
        ["sample_id", "n_transcripts", "tpm_spearman", "tpm_pearson_log2", "tpm_mae_log2", "fragment_spearman"],
    )

    truth_de = {r["gene_id"]: r for r in read_tsv(args.truth_dir / "gene_de_truth.tsv")}
    de_rows = []
    for result in read_tsv(args.de_results):
        gene_id = result["gene_id"]
        if gene_id not in truth_de:
            continue
        pvalue = as_float(result["pvalue"])
        padj = as_float(result["padj"])
        current_truth = truth_de[gene_id]
        de_rows.append({
            "gene_id": gene_id,
            "true_log2fc": float(current_truth["true_log2fc"]),
            "estimated_log2fc": float(result["log2FoldChange"]),
            "true_state": current_truth["true_state"],
            "effect_stratum": current_truth["effect_stratum"],
            "pvalue": "NA" if pvalue is None else pvalue,
            "padj": "NA" if padj is None else padj,
            "called": str(padj is not None and padj < 0.05).upper(),
            "true_de": current_truth["is_de"],
            "true_log2fc_jittered": float(current_truth["true_log2fc"]) + stable_jitter(gene_id),
        })
    write_tsv(
        args.output_dir / "gene_de.tsv",
        de_rows,
        ["gene_id", "true_log2fc", "estimated_log2fc", "true_state", "effect_stratum", "pvalue", "padj", "called", "true_de", "true_log2fc_jittered"],
    )

    ranked = sorted(
        de_rows,
        key=lambda row: (math.inf if row["pvalue"] == "NA" else float(row["pvalue"]), row["gene_id"]),
    )
    positives = sum(row["true_de"].upper() == "TRUE" for row in ranked)
    tp = fp = 0
    pr_rows = [{"rank": 0, "recall": 0.0, "precision": 1.0, "prevalence": positives / len(ranked)}]
    for rank, row in enumerate(ranked, start=1):
        if row["true_de"].upper() == "TRUE":
            tp += 1
        else:
            fp += 1
        pr_rows.append({
            "rank": rank,
            "recall": tp / positives,
            "precision": tp / (tp + fp),
            "prevalence": positives / len(ranked),
        })
    write_tsv(args.output_dir / "precision_recall.tsv", pr_rows, ["rank", "recall", "precision", "prevalence"])

    reproducibility_rows = [
        comparison_row("Clean HelixForge repeat", args.clean_comparison),
        comparison_row("Independent shared index", args.independent_comparison),
        comparison_row("Independent same-index repeat", args.reference_repeat_comparison),
    ]
    write_tsv(
        args.output_dir / "reproducibility.tsv",
        reproducibility_rows,
        ["arm", "strict_numeric_status", "deg_jaccard", "direction_concordance", "pvalue_rank_spearman", "top100_overlap"],
    )

    performance = json.loads(args.performance.read_text(encoding="utf-8"))
    process_totals: dict[str, float] = {}
    process_by_case: dict[tuple[str, str], dict] = {}
    for case in performance["cases"]:
        for process, values in case["trace"]["processes"].items():
            if process == "__all__":
                continue
            short_name = process.split(":")[-1]
            process_totals[short_name] = process_totals.get(short_name, 0.0) + values["summed_realtime_seconds"]
            key = (case["case"], short_name)
            current = process_by_case.setdefault(key, {
                "summed_realtime_seconds": 0.0,
                "peak_rss_bytes": 0,
                "task_count": 0,
            })
            current["summed_realtime_seconds"] += values["summed_realtime_seconds"]
            current["peak_rss_bytes"] = max(current["peak_rss_bytes"], values["peak_rss_bytes"])
            current["task_count"] += values["task_count"]
    selected = [name for name, _ in sorted(process_totals.items(), key=lambda item: item[1], reverse=True)[:12]]
    process_rows = []
    workflow_rows = []
    for case in performance["cases"]:
        all_tasks = case["trace"]["processes"]["__all__"]
        workflow_rows.append({
            "case": case["case"],
            "wall_seconds": case["workflow_wall_seconds"],
            "summed_realtime_seconds": all_tasks["summed_realtime_seconds"],
            "summed_scheduler_wait_seconds": all_tasks["summed_scheduler_wait_seconds"],
            "peak_running_concurrency": case["trace"]["peak_running_concurrency"],
        })
        for process in selected:
            values = process_by_case.get((case["case"], process), {})
            process_rows.append({
                "case": case["case"],
                "process": process,
                "summed_realtime_seconds": values.get("summed_realtime_seconds", 0),
                "peak_rss_mb": values.get("peak_rss_bytes", 0) / 1_000_000,
                "task_count": values.get("task_count", 0),
            })
    write_tsv(
        args.output_dir / "performance_process.tsv",
        process_rows,
        ["case", "process", "summed_realtime_seconds", "peak_rss_mb", "task_count"],
    )
    write_tsv(
        args.output_dir / "performance_workflow.tsv",
        workflow_rows,
        ["case", "wall_seconds", "summed_realtime_seconds", "summed_scheduler_wait_seconds", "peak_running_concurrency"],
    )

    de_metrics = metrics["differential_expression"]
    write_tsv(
        args.output_dir / "annotations.tsv",
        [{
            "auroc": de_metrics["auroc"],
            "auprc": de_metrics["auprc"],
            "prevalence": de_metrics["prevalence"],
            "log2fc_pearson": de_metrics["log2fc"]["pearson"],
            "log2fc_spearman": de_metrics["log2fc"]["spearman"],
            "direction_concordance": de_metrics["direction_concordance_de"],
        }],
        ["auroc", "auprc", "prevalence", "log2fc_pearson", "log2fc_spearman", "direction_concordance"],
    )
    print(json.dumps({"status": "pass", "genes": len(abundance_rows), "de_rows": len(de_rows)}))


if __name__ == "__main__":
    main()
