#!/usr/bin/env python3
"""Render dependency-free SVG figures from frozen Real Broad metrics."""

from __future__ import annotations

import argparse
import csv
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


def bar_svg(
    output: Path, title: str, ylabel: str, labels: list[str], values: list[float],
    *, value_format: str = ".3f", maximum: float | None = None, note: str | None = None,
) -> None:
    width, height = 960, 570
    left, right, top, bottom = 110, 35, 78, 125
    chart_width, chart_height = width - left - right, height - top - bottom
    maximum = maximum or max(values) * 1.15 or 1
    slot, bar_width = chart_width / len(values), chart_width / len(values) * 0.62
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<style>text{font-family:Arial,sans-serif;fill:#222}.title{font-size:24px;font-weight:bold}.axis{font-size:14px}.value{font-size:14px;font-weight:bold}.note{font-size:13px;fill:#555}</style>',
        f'<text x="{width / 2}" y="38" text-anchor="middle" class="title">{html.escape(title)}</text>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + chart_height}" stroke="#333"/>',
        f'<line x1="{left}" y1="{top + chart_height}" x2="{width - right}" y2="{top + chart_height}" stroke="#333"/>',
        f'<text x="24" y="{top + chart_height / 2}" text-anchor="middle" class="axis" transform="rotate(-90 24 {top + chart_height / 2})">{html.escape(ylabel)}</text>',
    ]
    for tick in range(6):
        fraction = tick / 5
        y = top + chart_height * (1 - fraction)
        parts.extend([
            f'<line x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}" stroke="#ddd"/>',
            f'<text x="{left - 12}" y="{y + 5:.1f}" text-anchor="end" class="axis">{maximum * fraction:.2g}</text>',
        ])
    for index, (label, value) in enumerate(zip(labels, values)):
        x = left + slot * index + (slot - bar_width) / 2
        bar_height = chart_height * value / maximum
        y = top + chart_height - bar_height
        parts.extend([
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width:.1f}" height="{bar_height:.1f}" fill="{COLORS[index % len(COLORS)]}"/>',
            f'<text x="{x + bar_width / 2:.1f}" y="{max(top + 16, y - 8):.1f}" text-anchor="middle" class="value">{html.escape(format(value, value_format))}</text>',
            f'<text x="{x + bar_width / 2:.1f}" y="{top + chart_height + 28}" text-anchor="middle" class="axis">{html.escape(label)}</text>',
        ])
    if note:
        parts.append(f'<text x="{width / 2}" y="{height - 24}" text-anchor="middle" class="note">{html.escape(note)}</text>')
    parts.append("</svg>\n")
    output.write_text("\n".join(parts), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metrics", required=True, type=Path)
    parser.add_argument("--null-overlap", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    metrics = json.loads(args.metrics.read_text(encoding="utf-8"))
    with args.null_overlap.open(encoding="utf-8", newline="") as handle:
        null_overlaps = sorted(int(row["overlap_bp"]) for row in csv.DictReader(handle, delimiter="\t"))

    widths = metrics["counts_and_widths"]
    outputs = [args.output_dir / "figure_1_domain_counts.svg"]
    bar_svg(outputs[-1], "K562 H3K27me3 broad-domain sets", "Intervals", ["Replicate 1", "Replicate 2", "Consensus", "ENCODE ref."], [widths["replicate_1"]["count"], widths["replicate_2"]["count"], widths["consensus"]["count"], widths["encode_reference"]["count"]], value_format=",.0f")

    coverage = metrics["replicate_coverage"]
    outputs.append(args.output_dir / "figure_2_coverage_concordance.svg")
    bar_svg(outputs[-1], "Replicate CPM coverage concordance", "Correlation", ["Pearson", "Rotated Pearson", "Spearman", "Rotated Spearman"], [coverage["pearson"], coverage["rotated_pearson"], coverage["spearman"], coverage["rotated_spearman"]], maximum=0.55, note=f"{coverage['bins']:,} non-overlapping 500 bp bins; rotation seed frozen before evaluation")

    frip = metrics["frip"]
    outputs.append(args.output_dir / "figure_3_frip.svg")
    bar_svg(outputs[-1], "Fraction of reads in broad peaks", "FRiP", ["Replicate 1", "Replicate 2"], [frip["ENCFF000BXP"]["frip"], frip["ENCFF000BXN"]["frip"]], maximum=0.40)

    overlap = metrics["encode_overlap"]
    null_median = null_overlaps[len(null_overlaps) // 2]
    null_p95 = null_overlaps[int(0.95 * (len(null_overlaps) - 1))]
    outputs.append(args.output_dir / "figure_4_encode_overlap.svg")
    bar_svg(outputs[-1], "Consensus overlap with ENCODE replicated peaks", "Overlap (bp)", ["Observed", "Null median", "Null p95", "Null maximum"], [overlap["observed_overlap_bp"], null_median, null_p95, max(null_overlaps)], value_format=",.0f", note=f"0/100 rotations reached observed overlap; empirical p = {overlap['empirical_p']:.4f}")

    annotation = metrics["annotation_distribution"]
    outputs.append(args.output_dir / "figure_5_annotation.svg")
    bar_svg(outputs[-1], "Genomic annotation of support=2 consensus", "Consensus domains", ["Promoter", "Exon", "Intron/gene", "Intergenic"], [annotation["promoter"], annotation["exon"], annotation["intron_or_gene_body"], annotation["intergenic"]], value_format=",.0f")

    fragmentation = metrics["external_fragmentation_context"]
    outputs.append(args.output_dir / "figure_6_fragmentation_context.svg")
    bar_svg(outputs[-1], "Broad-domain fragmentation context", "Fragmentation rate", ["Synthetic truth", "Real: all ENCODE", "Real: touched ENCODE"], [metrics["synthetic_broad_fragmentation_reference"], fragmentation["fragmentation_rate_all_external"], fragmentation["fragmentation_rate_touched_external"]], maximum=0.70, note="Real ENCODE calls are descriptive reference, not ground truth; rates are not directly interchangeable")

    manifest = {
        "schema_version": "1.0", "type": "real_broad_figures",
        "renderer": "dependency-free SVG", "python": platform.python_version(),
        "inputs": {args.metrics.name: sha256(args.metrics), args.null_overlap.name: sha256(args.null_overlap)},
        "outputs": [{"path": path.name, "sha256": sha256(path), "size_bytes": path.stat().st_size} for path in outputs],
    }
    (args.output_dir / "figures_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
