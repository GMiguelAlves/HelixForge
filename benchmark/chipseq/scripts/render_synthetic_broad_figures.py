#!/usr/bin/env python3
"""Render scientific figures from frozen synthetic-broad metric tables."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


LABELS = {
    "helixforge_rep1": "HelixForge rep1",
    "helixforge_rep2": "HelixForge rep2",
    "helixforge_consensus": "HelixForge consensus",
    "independent_rep1": "Independent rep1",
    "independent_rep2": "Independent rep2",
    "independent_consensus": "Independent consensus",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def save_figure(figure: plt.Figure, output: Path) -> list[Path]:
    paths = []
    for suffix in (".png", ".pdf"):
        path = output.with_suffix(suffix)
        figure.savefig(path, dpi=180, bbox_inches="tight")
        paths.append(path)
    plt.close(figure)
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metrics-dir", required=True, type=Path)
    parser.add_argument("--coverage-tsv", required=True, type=Path)
    parser.add_argument("--primary-label", default="helixforge_consensus")
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)

    accuracy = read_tsv(args.metrics_dir / "truth_accuracy.tsv")
    signal = read_tsv(args.metrics_dir / "signal_class_metrics.tsv")
    width = read_tsv(args.metrics_dir / "width_class_metrics.tsv")
    repeats = read_tsv(args.metrics_dir / "repeat_overlap_metrics.tsv")
    pairs = read_tsv(args.metrics_dir / "replicate_and_external_metrics.tsv")
    coverage = read_tsv(args.coverage_tsv)
    outputs: list[Path] = []

    metrics = ("base_precision", "base_recall", "base_f1", "global_iou")
    figure, axis = plt.subplots(figsize=(10.5, 5.6))
    bar_width = 0.8 / len(accuracy)
    for index, row in enumerate(accuracy):
        positions = [position - 0.4 + bar_width / 2 + index * bar_width for position in range(len(metrics))]
        axis.bar(positions, [float(row[metric]) for metric in metrics], width=bar_width, label=LABELS[row["peak_set"]])
    axis.set_xticks(range(len(metrics)), ("Precision", "Recall", "F1", "Global IoU"))
    axis.set(ylabel="Fraction", ylim=(0, 1.02), title="Broad-domain ground-truth accuracy")
    axis.legend(fontsize=7, ncol=2)
    outputs.extend(save_figure(figure, args.output_dir / "figure_1_ground_truth_accuracy"))

    primary_signal = [row for row in signal if row["peak_set"] == args.primary_label]
    primary_signal.sort(key=lambda row: ("STRONG", "MEDIUM", "WEAK").index(row["signal_class"]))
    figure, axis = plt.subplots(figsize=(7.2, 5.2))
    positions = range(len(primary_signal))
    axis.bar([value - 0.18 for value in positions], [float(row["region_recall"]) for row in primary_signal], 0.36, label="Region recall")
    axis.bar([value + 0.18 for value in positions], [float(row["per_domain_iou_median"]) for row in primary_signal], 0.36, label="Median domain IoU")
    axis.set_xticks(list(positions), [row["signal_class"] for row in primary_signal])
    axis.set(ylabel="Fraction", ylim=(0, 1.02), title="HelixForge consensus by signal strength")
    axis.legend()
    outputs.extend(save_figure(figure, args.output_dir / "figure_2_signal_classes"))

    primary_width = [row for row in width if row["peak_set"] == args.primary_label]
    primary_width.sort(key=lambda row: ("SHORT_BROAD", "MEDIUM_BROAD", "LONG_BROAD").index(row["width_class"]))
    figure, axis = plt.subplots(figsize=(7.5, 5.2))
    positions = range(len(primary_width))
    axis.bar([value - 0.18 for value in positions], [float(row["region_recall"]) for row in primary_width], 0.36, label="Region recall")
    axis.bar([value + 0.18 for value in positions], [float(row["per_domain_iou_median"]) for row in primary_width], 0.36, label="Median domain IoU")
    axis.set_xticks(list(positions), [row["width_class"].replace("_BROAD", "") for row in primary_width])
    axis.set(ylabel="Fraction", ylim=(0, 1.02), title="HelixForge consensus by domain width")
    axis.legend()
    outputs.extend(save_figure(figure, args.output_dir / "figure_3_width_classes"))

    figure, axis = plt.subplots(figsize=(10.2, 5.6))
    positions = range(len(accuracy))
    axis.bar([value - 0.18 for value in positions], [float(row["fragmentation_rate"]) for row in accuracy], 0.36, label="Fragmentation rate")
    axis.bar([value + 0.18 for value in positions], [float(row["merging_rate"]) for row in accuracy], 0.36, label="Merging rate")
    axis.axhline(0.30, color="#d62728", linestyle="--", linewidth=1.2, label="Frozen 0.30 limit")
    axis.set_xticks(list(positions), [LABELS[row["peak_set"]] for row in accuracy], rotation=25, ha="right")
    axis.set(ylabel="Fraction", ylim=(0, max(0.7, max(float(row["fragmentation_rate"]) for row in accuracy) + 0.05)), title="Broad-domain topology")
    axis.legend()
    outputs.extend(save_figure(figure, args.output_dir / "figure_4_fragmentation_merging"))

    primary_quartiles = [
        row for row in repeats
        if row["peak_set"] == args.primary_label and row["analysis"] == "quartile" and row["metric"] in {"coverage_recall", "per_domain_iou"}
    ]
    figure, axis = plt.subplots(figsize=(7.2, 5.2))
    for metric, label, color in (("coverage_recall", "Mean coverage recall", "#4c78a8"), ("per_domain_iou", "Mean domain IoU", "#f58518")):
        selected = sorted((row for row in primary_quartiles if row["metric"] == metric), key=lambda row: row["group"])
        axis.plot([row["group"] for row in selected], [float(row["mean"]) for row in selected], marker="o", label=label, color=color)
    axis.set(xlabel="Repeat-overlap quartile", ylabel="Fraction", ylim=(0, 1.02), title="Recovery across repeat-overlap strata")
    axis.legend()
    outputs.extend(save_figure(figure, args.output_dir / "figure_5_repeat_overlap"))

    figure, axis = plt.subplots(figsize=(9.0, 5.2))
    pair_labels = [f"{LABELS.get(row['left'], row['left'])}\nvs\n{LABELS.get(row['right'], row['right'])}" for row in pairs]
    bars = axis.bar(pair_labels, [float(row["base_jaccard"]) for row in pairs], color="#54a24b")
    axis.bar_label(bars, fmt="%.3f", fontsize=8)
    axis.set(ylabel="Base Jaccard", ylim=(0, 1.03), title="Replicate and independent-path concordance")
    axis.tick_params(axis="x", labelsize=7)
    outputs.extend(save_figure(figure, args.output_dir / "figure_6_path_concordance"))

    expected_rows = [row for row in coverage if row["left"] == "expected_signal"]
    figure, axis = plt.subplots(figsize=(8.4, 5.2))
    bars = axis.bar([LABELS.get(row["right"], row["right"]) for row in expected_rows], [float(row["spearman"]) for row in expected_rows], color="#b279a2")
    axis.bar_label(bars, fmt="%.3f", fontsize=8)
    axis.set(ylabel="Spearman correlation", ylim=(-1, 1), title="Expected broad signal versus CPM coverage")
    axis.tick_params(axis="x", rotation=20)
    outputs.extend(save_figure(figure, args.output_dir / "figure_7_coverage_signal"))

    inputs = sorted(args.metrics_dir.glob("*.tsv")) + [args.coverage_tsv]
    manifest = {
        "schema_version": "1.0",
        "type": "synthetic_broad_figures",
        "primary_label": args.primary_label,
        "python": platform.python_version(),
        "matplotlib": matplotlib.__version__,
        "inputs": {path.name: sha256(path) for path in inputs},
        "outputs": [{"path": path.name, "sha256": sha256(path), "size_bytes": path.stat().st_size} for path in outputs],
    }
    (args.output_dir / "figures_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
