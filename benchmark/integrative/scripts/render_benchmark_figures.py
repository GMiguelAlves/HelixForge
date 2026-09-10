#!/usr/bin/env python3
"""Render deterministic SVG figures from the frozen Integrative benchmark metrics."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
import re
from pathlib import Path


WIDTH = 1120
INK = "#172033"
MUTED = "#5b6475"
GRID = "#d9dee8"
PASS = "#238636"
LIMITED = "#bf8700"
FAIL = "#cf222e"
NA = "#6e7781"
BLUE = "#0969da"
PURPLE = "#8250df"


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def start_svg(title: str, description: str, height: int) -> list[str]:
    return [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}" role="img" aria-labelledby="title desc">',
        f'<title id="title">{esc(title)}</title>',
        f'<desc id="desc">{esc(description)}</desc>',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<style>text{font-family:Arial,Helvetica,sans-serif;fill:#172033}.title{font-size:26px;font-weight:700}.subtitle{font-size:14px;fill:#5b6475}.label{font-size:15px;font-weight:600}.value{font-size:14px}.small{font-size:12px;fill:#5b6475}.axis{stroke:#d9dee8;stroke-width:1}.status{font-size:13px;font-weight:700;fill:#ffffff}</style>',
        f'<text x="48" y="46" class="title">{esc(title)}</text>',
        f'<text x="48" y="72" class="subtitle">{esc(description)}</text>',
    ]


def write_svg(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join([*lines, "</svg>", ""]), encoding="utf-8", newline="\n")


def load_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def render_arm_status(rows: list[dict[str, str]], output: Path) -> None:
    labels = {
        "synthetic_ground_truth": "Synthetic ground truth",
        "manifest_reentry": "Manifest re-entry",
        "negative_contracts": "Negative contracts",
        "real_biological": "Real biological integration",
    }
    lines = start_svg(
        "Integrative benchmark classification",
        "Four frozen arms; all core release gates passed",
        430,
    )
    lines.extend([
        '<text x="48" y="112" class="small">BENCHMARK ARM</text>',
        '<text x="650" y="112" class="small">CORE GATES</text>',
        '<text x="840" y="112" class="small">CLASSIFICATION</text>',
    ])
    for index, row in enumerate(rows):
        y = 145 + index * 66
        status = row["overall_classification"]
        color = PASS if status == "PASS" else LIMITED
        lines.extend([
            f'<rect x="40" y="{y - 27}" width="1040" height="52" rx="8" fill="#f6f8fa" stroke="{GRID}"/>',
            f'<text x="58" y="{y + 5}" class="label">{esc(labels[row["arm_id"]])}</text>',
            f'<rect x="650" y="{y - 16}" width="88" height="30" rx="15" fill="{PASS}"/>',
            f'<text x="694" y="{y + 5}" class="status" text-anchor="middle">PASS</text>',
            f'<rect x="840" y="{y - 16}" width="210" height="30" rx="15" fill="{color}"/>',
            f'<text x="945" y="{y + 5}" class="status" text-anchor="middle">{esc(status)}</text>',
        ])
    lines.append('<text x="48" y="408" class="small">Global baseline: PASS_WITH_LIMITATIONS because IB4 and IB5 are preserved as expected-range limitations.</text>')
    write_svg(output / "benchmark_arm_status.svg", lines)


def criterion_count(specification: str) -> int:
    match = re.fullmatch(r"([A-Z]+)(\d+)-([A-Z]+)(\d+)", specification)
    if not match or match.group(1) != match.group(3):
        raise ValueError(f"Unsupported criterion range: {specification}")
    return int(match.group(4)) - int(match.group(2)) + 1


def render_acceptance(rows: list[dict[str, str]], real_rows: list[dict[str, str]], output: Path) -> None:
    real_counts = {"PASS": 0, "FAIL": 0, "NOT_EVALUABLE": 0}
    for row in real_rows:
        real_counts[row["status"]] += 1
    counts = []
    labels = ["Synthetic", "Re-entry", "Contracts", "Real biological"]
    for row in rows[:3]:
        total = criterion_count(row["frozen_criteria"])
        counts.append({"PASS": total, "FAIL": 0, "NOT_EVALUABLE": 0})
    counts.append(real_counts)
    lines = start_svg(
        "Frozen acceptance criteria",
        "Status counts from IS1–IS12, IR1–IR4, IC1–IC6 and IB1–IB8",
        470,
    )
    plot_x, plot_w, maximum = 260, 760, 12
    for tick in range(0, maximum + 1, 2):
        x = plot_x + plot_w * tick / maximum
        lines.extend([
            f'<line x1="{x:.1f}" y1="112" x2="{x:.1f}" y2="390" class="axis"/>',
            f'<text x="{x:.1f}" y="414" class="small" text-anchor="middle">{tick}</text>',
        ])
    colors = [("PASS", PASS), ("FAIL", FAIL), ("NOT_EVALUABLE", NA)]
    for index, (label, values) in enumerate(zip(labels, counts)):
        y = 140 + index * 68
        lines.append(f'<text x="48" y="{y + 22}" class="label">{esc(label)}</text>')
        cursor = plot_x
        for key, color in colors:
            value = values[key]
            if not value:
                continue
            width = plot_w * value / maximum
            lines.append(f'<rect x="{cursor:.1f}" y="{y}" width="{width:.1f}" height="34" fill="{color}"/>')
            lines.append(f'<text x="{cursor + width / 2:.1f}" y="{y + 23}" class="status" text-anchor="middle">{value}</text>')
            cursor += width
    lines.extend([
        f'<rect x="48" y="438" width="14" height="14" fill="{PASS}"/><text x="70" y="450" class="small">PASS</text>',
        f'<rect x="150" y="438" width="14" height="14" fill="{FAIL}"/><text x="172" y="450" class="small">FAIL</text>',
        f'<rect x="238" y="438" width="14" height="14" fill="{NA}"/><text x="260" y="450" class="small">NOT_EVALUABLE</text>',
    ])
    write_svg(output / "acceptance_criteria_status.svg", lines)


def duration_label(seconds: float) -> str:
    if seconds >= 60:
        return f"{seconds / 60:.1f} min"
    return f"{seconds:.1f} s"


def render_runtime(performance: list[dict[str, object]], output: Path) -> None:
    lines = start_svg(
        "Descriptive execution time",
        "Shared-cluster wall time; logarithmic axis, not a controlled speed comparison",
        470,
    )
    plot_x, plot_w = 310, 700
    maximum = max(float(item["wall_seconds"]) for item in performance)
    log_max = math.log10(maximum + 1)
    for index, item in enumerate(performance):
        seconds = float(item["wall_seconds"])
        width = plot_w * math.log10(seconds + 1) / log_max
        y = 125 + index * 70
        lines.extend([
            f'<text x="48" y="{y + 23}" class="label">{esc(item["label"])}</text>',
            f'<rect x="{plot_x}" y="{y}" width="{width:.1f}" height="34" rx="5" fill="{BLUE}"/>',
            f'<text x="{min(plot_x + width + 12, 1030):.1f}" y="{y + 23}" class="value">{esc(duration_label(seconds))}</text>',
        ])
    lines.append('<text x="48" y="430" class="small">Synthetic and re-entry values are means of two runs; contracts cover two iterations; real integration is approximate workflow wall time.</text>')
    write_svg(output / "runtime_overview.svg", lines)


def render_real_metrics(real: dict[str, object], output: Path) -> None:
    lines = start_svg(
        "Real biological integration metrics",
        "GSE133183 frozen outputs; descriptive values without post-hoc threshold changes",
        650,
    )
    master = int(real["master_genes"])
    rna = int(real["master_state_counts"]["rna"]["MEASURED"])
    chip = int(real["master_state_counts"]["chip"]["MEASURED"])
    lines.extend([
        '<text x="48" y="118" class="label">Evidence coverage</text>',
        f'<text x="48" y="153" class="value">RNA measured</text><rect x="220" y="134" width="{650 * rna / master:.1f}" height="24" fill="{BLUE}"/><text x="890" y="153" class="value">{rna:,} / {master:,} ({100 * rna / master:.1f}%)</text>',
        f'<text x="48" y="195" class="value">ChIP measured</text><rect x="220" y="176" width="{650 * chip / master:.1f}" height="24" fill="{PURPLE}"/><text x="890" y="195" class="value">{chip:,} / {master:,} ({100 * chip / master:.1f}%)</text>',
        '<line x1="48" y1="232" x2="1072" y2="232" class="axis"/>',
        '<text x="48" y="270" class="label">Significant differential-binding regions</text>',
    ])
    binding = real["differential_binding"]
    ac = int(binding["H3K27ac"]["significant"])
    me3 = int(binding["H3K27me3"].get("significant", 0))
    maximum = max(ac, me3, 1)
    for index, (label, value, color) in enumerate([("H3K27ac", ac, BLUE), ("H3K27me3", me3, PURPLE)]):
        y = 292 + index * 42
        width = 650 * value / maximum
        lines.extend([
            f'<text x="48" y="{y + 20}" class="value">{label}</text>',
            f'<rect x="220" y="{y}" width="{max(width, 2):.1f}" height="24" fill="{color}"/>',
            f'<text x="890" y="{y + 20}" class="value">{value:,}</text>',
        ])
    lines.extend([
        '<line x1="48" y1="392" x2="1072" y2="392" class="axis"/>',
        '<text x="48" y="430" class="label">Regulatory interpretation records</text>',
    ])
    patterns = real["regulatory_pattern_counts"]
    pattern_values = [
        ("Concordant activation", int(patterns["CONCORDANT_ACTIVATION"]), PASS),
        ("Concordant repression", int(patterns["CONCORDANT_REPRESSION"]), BLUE),
        ("Discordant", int(patterns["DISCORDANT"]), FAIL),
    ]
    pattern_max = max(value for _label, value, _color in pattern_values)
    for index, (label, value, color) in enumerate(pattern_values):
        y = 452 + index * 44
        width = 650 * value / pattern_max
        lines.extend([
            f'<text x="48" y="{y + 20}" class="value">{esc(label)}</text>',
            f'<rect x="220" y="{y}" width="{width:.1f}" height="24" fill="{color}"/>',
            f'<text x="890" y="{y + 20}" class="value">{value:,}</text>',
        ])
    lines.append('<text x="48" y="625" class="small">IB4 remains FAIL because H3K27me3 has zero significant regions; IB5 remains NOT_EVALUABLE.</text>')
    write_svg(output / "real_biological_metrics.svg", lines)


def render(repo_root: Path, output: Path) -> None:
    results = repo_root / "benchmark/integrative/results"
    rows = load_tsv(results / "integrative_benchmark_matrix.tsv")
    real_rows = load_tsv(results / "real/evaluation/acceptance_results.tsv")
    summary = json.loads((results / "integrative_benchmark_summary.json").read_text(encoding="utf-8"))
    real = json.loads((results / "real/evaluation/benchmark_summary.json").read_text(encoding="utf-8"))
    output.mkdir(parents=True, exist_ok=True)
    render_arm_status(rows, output)
    render_acceptance(rows, real_rows, output)
    render_runtime(summary["performance"], output)
    render_real_metrics(real, output)
    figures = sorted(output.glob("*.svg"))
    checksum_lines = [f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}" for path in figures]
    (output / "SHA256SUMS").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    output = args.output_dir or args.repo_root / "benchmark/integrative/figures/baseline"
    render(args.repo_root.resolve(), output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
