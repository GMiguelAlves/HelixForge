#!/usr/bin/env python3
"""Render scientific figures from frozen synthetic-narrow metric tables."""

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


COLORS = {"STRONG": "#1b9e77", "MEDIUM": "#d95f02", "WEAK": "#7570b3"}


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
    files = []
    for suffix in (".png", ".pdf"):
        path = output.with_suffix(suffix)
        figure.savefig(path, dpi=180, bbox_inches="tight")
        files.append(path)
    plt.close(figure)
    return files


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metrics-dir", required=True, type=Path)
    parser.add_argument("--primary-label", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    accuracy = read_tsv(args.metrics_dir / "truth_accuracy.tsv")
    classes = read_tsv(args.metrics_dir / "signal_class_metrics.tsv")
    matches = read_tsv(args.metrics_dir / "matched_peaks.tsv")
    curves = read_tsv(args.metrics_dir / "precision_recall_curve.tsv")
    replicates = read_tsv(args.metrics_dir / "replicate_metrics.tsv")
    outputs = []

    figure, axis = plt.subplots(figsize=(6.4, 5.2))
    for label in sorted({row["peak_set"] for row in curves}):
        selected = [row for row in curves if row["peak_set"] == label]
        axis.step([float(row["recall"]) for row in selected], [float(row["precision"]) for row in selected], where="post", label=label)
    axis.axhline(0.5, color="#777777", linestyle="--", linewidth=1, label="prevalence baseline")
    axis.set(xlabel="Recall", ylabel="Precision", xlim=(0, 1.01), ylim=(0, 1.01), title="Candidate-panel precision–recall")
    axis.legend(fontsize=7)
    outputs.extend(save_figure(figure, args.output_dir / "figure_1_precision_recall"))

    labels = sorted({row["peak_set"] for row in classes})
    figure, axis = plt.subplots(figsize=(7.2, 5.2))
    width = 0.8 / max(1, len(labels))
    for label_index, label in enumerate(labels):
        selected = {row["signal_class"]: float(row["recall"]) for row in classes if row["peak_set"] == label}
        positions = [index - 0.4 + width / 2 + label_index * width for index in range(3)]
        axis.bar(positions, [selected[name] for name in ("STRONG", "MEDIUM", "WEAK")], width=width, label=label)
    axis.set_xticks(range(3), ("STRONG", "MEDIUM", "WEAK"))
    axis.set(xlabel="Frozen signal class", ylabel="Recall", ylim=(0, 1.01), title="Recovery by simulated signal strength")
    axis.legend(fontsize=7)
    outputs.extend(save_figure(figure, args.output_dir / "figure_2_signal_class_recall"))

    primary_matches = [row for row in matches if row["peak_set"] == args.primary_label]
    summit = [float(row["summit_distance_bp"]) for row in primary_matches]
    figure, axis = plt.subplots(figsize=(6.4, 5.2))
    axis.hist(summit, bins=40, color="#4c78a8", edgecolor="white")
    axis.axvline(100, color="#e45756", linestyle="--", label="100 bp criterion")
    axis.set(xlabel="Absolute summit distance (bp)", ylabel="Matched peaks", title=f"Summit localization — {args.primary_label}")
    axis.legend()
    outputs.extend(save_figure(figure, args.output_dir / "figure_3_summit_distance"))

    figure, axis = plt.subplots(figsize=(6.4, 5.2))
    values = []
    names = []
    for signal_class in ("WEAK", "MEDIUM", "STRONG"):
        rows = [float(row["called_signal"]) for row in primary_matches if row["signal_class"] == signal_class]
        values.append(rows)
        names.append(signal_class)
    boxes = axis.boxplot(values, labels=names, patch_artist=True, showfliers=False)
    for patch, signal_class in zip(boxes["boxes"], names):
        patch.set_facecolor(COLORS[signal_class])
        patch.set_alpha(0.75)
    axis.set(xlabel="Frozen true-signal class", ylabel="MACS3 signalValue", title=f"True signal versus called rank proxy — {args.primary_label}")
    outputs.extend(save_figure(figure, args.output_dir / "figure_4_signal_ranking"))

    if replicates:
        row = replicates[0]
        names = ["Base Jaccard", "Rep1 reciprocal", "Rep2 reciprocal", "Rank Spearman"]
        values = [float(row["base_jaccard"]), float(row["left_reciprocal_overlap"]), float(row["right_reciprocal_overlap"]), float(row["rank_spearman"])]
        figure, axis = plt.subplots(figsize=(7.2, 5.2))
        axis.bar(names, values, color="#72b7b2")
        axis.set(ylabel="Fraction / correlation", ylim=(min(0, min(values) - 0.1), 1.01), title="Replicate concordance")
        axis.tick_params(axis="x", rotation=20)
        outputs.extend(save_figure(figure, args.output_dir / "figure_5_replicate_concordance"))

    figure, axis = plt.subplots(figsize=(7.2, 5.2))
    peak_labels = [row["peak_set"] for row in accuracy]
    peak_counts = [int(row["called_peaks"]) for row in accuracy]
    bars = axis.bar(peak_labels, peak_counts, color="#f58518")
    axis.bar_label(bars, fontsize=7)
    axis.set(ylabel="Peak count", title="Replicate and IDR peak-set sizes")
    axis.tick_params(axis="x", rotation=25)
    outputs.extend(save_figure(figure, args.output_dir / "figure_6_peak_set_counts"))

    manifest = {
        "schema_version": "1.0", "type": "synthetic_narrow_figures", "primary_label": args.primary_label,
        "python": platform.python_version(), "matplotlib": matplotlib.__version__,
        "inputs": {path.name: sha256(path) for path in sorted(args.metrics_dir.glob("*.tsv"))},
        "outputs": [{"path": path.name, "sha256": sha256(path), "size_bytes": path.stat().st_size} for path in outputs],
    }
    (args.output_dir / "figures_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
