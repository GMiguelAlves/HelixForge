#!/usr/bin/env python3
"""Render dependency-free SVG figures from frozen Real Narrow metrics."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import platform
from pathlib import Path


COLORS = ("#4c78a8", "#f58518", "#54a24b", "#b279a2", "#e45756")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def bar_svg(output: Path, title: str, ylabel: str, labels: list[str], values: list[float], *, value_format: str = ".3f", maximum: float | None = None, note: str | None = None) -> None:
    width, height = 900, 560
    left, right, top, bottom = 105, 35, 78, 118
    chart_width = width - left - right
    chart_height = height - top - bottom
    maximum = maximum or max(values) * 1.15 or 1
    slot = chart_width / len(values)
    bar_width = slot * 0.62
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<style>text{font-family:Arial,sans-serif;fill:#222}.title{font-size:24px;font-weight:bold}.axis{font-size:15px}.value{font-size:15px;font-weight:bold}.note{font-size:14px;fill:#555}</style>',
        f'<text x="{width / 2}" y="38" text-anchor="middle" class="title">{html.escape(title)}</text>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + chart_height}" stroke="#333"/>',
        f'<line x1="{left}" y1="{top + chart_height}" x2="{width - right}" y2="{top + chart_height}" stroke="#333"/>',
        f'<text x="24" y="{top + chart_height / 2}" text-anchor="middle" class="axis" transform="rotate(-90 24 {top + chart_height / 2})">{html.escape(ylabel)}</text>',
    ]
    for tick in range(6):
        fraction = tick / 5
        y = top + chart_height * (1 - fraction)
        value = maximum * fraction
        parts.extend([
            f'<line x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}" stroke="#ddd"/>',
            f'<text x="{left - 12}" y="{y + 5:.1f}" text-anchor="end" class="axis">{value:.2g}</text>',
        ])
    for index, (label, value) in enumerate(zip(labels, values)):
        x = left + slot * index + (slot - bar_width) / 2
        bar_height = chart_height * value / maximum
        y = top + chart_height - bar_height
        display = format(value, value_format)
        parts.extend([
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width:.1f}" height="{bar_height:.1f}" fill="{COLORS[index % len(COLORS)]}"/>',
            f'<text x="{x + bar_width / 2:.1f}" y="{max(top + 16, y - 8):.1f}" text-anchor="middle" class="value">{html.escape(display)}</text>',
            f'<text x="{x + bar_width / 2:.1f}" y="{top + chart_height + 27}" text-anchor="middle" class="axis">{html.escape(label)}</text>',
        ])
    if note:
        parts.append(f'<text x="{width / 2}" y="{height - 24}" text-anchor="middle" class="note">{html.escape(note)}</text>')
    parts.append("</svg>\n")
    output.write_text("\n".join(parts), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metrics", required=True, type=Path)
    parser.add_argument("--capacity", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    metrics = json.loads(args.metrics.read_text(encoding="utf-8"))
    capacity = json.loads(args.capacity.read_text(encoding="utf-8"))

    qc = metrics["peak_qc"]
    outputs = [args.output_dir / "figure_1_peak_counts.svg"]
    bar_svg(outputs[-1], "K562 CTCF peak recovery and IDR set", "Peak count", ["Replicate 1", "Replicate 2", "IDR"], [qc["replicate_1_peaks"], qc["replicate_2_peaks"], qc["idr_peaks"]], value_format=",.0f")

    concordance = metrics["replicate_concordance"]
    outputs.append(args.output_dir / "figure_2_replicate_qc.svg")
    bar_svg(outputs[-1], "Replicate concordance and FRiP", "Fraction / correlation", ["Base Jaccard", "Rank Spearman", "FRiP R1", "FRiP R2"], [concordance["base_jaccard"], concordance["rank_spearman"], qc["replicate_1_frip"], qc["replicate_2_frip"]], maximum=1.0)

    motif = metrics["motif"]
    outputs.append(args.output_dir / "figure_3_ctcf_motif.svg")
    bar_svg(outputs[-1], "Canonical CTCF motif enrichment (MA0139.1)", "Median maximum PWM log-odds", ["IDR peaks", "Matched controls"], [motif["peak_score_median"], motif["control_score_median"]], value_format=".2f", note=f"Central ±25 bp: {motif['central_window_fraction']:.1%}; BH-adjusted p < 1e-300")

    annotation = metrics["annotation_distribution"]
    outputs.append(args.output_dir / "figure_4_annotation.svg")
    bar_svg(outputs[-1], "Genomic annotation of reproducible CTCF peaks", "IDR peaks", ["Promoter", "Exon", "Intron/gene body", "Intergenic"], [annotation["promoter"], annotation["exon"], annotation["intron_or_gene_body"], annotation["intergenic"]], value_format=",.0f")

    ratios = capacity["capacity_ratio"]
    outputs.append(args.output_dir / "figure_5_rn3_capacity.svg")
    bar_svg(outputs[-1], "RN3 exact-GC capacity preflight", "Candidate capacity ratio M/k", ["Minimum", "P01", "P05", "Median", "P95"], [ratios["minimum"], ratios["p01"], ratios["p05"], ratios["median"], ratios["p95"]], value_format=".0f", maximum=10, note=f"NOT EVALUABLE: {capacity['strata_with_M_lt_k']:,} / {capacity['number_of_strata']:,} strata had M < k; no nulls generated")

    manifest = {
        "schema_version": "1.0",
        "type": "real_narrow_figures",
        "renderer": "dependency-free SVG",
        "python": platform.python_version(),
        "inputs": {args.metrics.name: sha256(args.metrics), args.capacity.name: sha256(args.capacity)},
        "outputs": [{"path": path.name, "sha256": sha256(path), "size_bytes": path.stat().st_size} for path in outputs],
    }
    (args.output_dir / "figures_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
