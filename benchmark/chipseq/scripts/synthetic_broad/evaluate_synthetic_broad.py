#!/usr/bin/env python3
"""Evaluate frozen synthetic broad domain sets without post-hoc choices."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Domain:
    index: int
    domain_id: str
    chrom: str
    start: int
    end: int
    width_class: str
    signal_class: str
    signal_strength: float
    repeat_overlap_bp: int
    repeat_overlap_fraction: float


@dataclass(frozen=True)
class Call:
    index: int
    chrom: str
    start: int
    end: int
    identifier: str
    signal: float


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] * (upper - position) + ordered[upper] * (position - lower)


def ranks(values: list[float]) -> list[float]:
    result = [0.0] * len(values)
    order = sorted(range(len(values)), key=lambda index: (values[index], index))
    cursor = 0
    while cursor < len(order):
        end = cursor + 1
        while end < len(order) and values[order[end]] == values[order[cursor]]:
            end += 1
        rank = (cursor + end - 1) / 2 + 1
        for position in order[cursor:end]:
            result[position] = rank
        cursor = end
    return result


def pearson(left: list[float], right: list[float]) -> float | None:
    if len(left) != len(right) or len(left) < 2:
        return None
    mean_left, mean_right = statistics.fmean(left), statistics.fmean(right)
    numerator = sum((a - mean_left) * (b - mean_right) for a, b in zip(left, right))
    left_ss = sum((a - mean_left) ** 2 for a in left)
    right_ss = sum((b - mean_right) ** 2 for b in right)
    return numerator / math.sqrt(left_ss * right_ss) if left_ss and right_ss else None


def spearman(left: list[float], right: list[float]) -> float | None:
    return pearson(ranks(left), ranks(right)) if len(left) == len(right) else None


def write_tsv(path: Path, rows: list[dict], columns: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def parse_truth(path: Path) -> list[Domain]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    domains = [
        Domain(
            index=index,
            domain_id=row["domain_id"],
            chrom=row["chrom"],
            start=int(row["start"]),
            end=int(row["end"]),
            width_class=row["width_class"].upper(),
            signal_class=row["signal_class"].upper(),
            signal_strength=float(row["signal_strength"]),
            repeat_overlap_bp=int(row["repeat_overlap_bp"]),
            repeat_overlap_fraction=float(row["repeat_overlap_fraction"]),
        )
        for index, row in enumerate(rows)
    ]
    if len(domains) != 360 or len({row.domain_id for row in domains}) != 360:
        raise ValueError("truth must contain exactly 360 unique broad domains")
    return domains


def parse_calls(path: Path, eligible_contigs: dict[str, int]) -> tuple[list[Call], int]:
    calls, outside = [], 0
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip() or line.startswith("#"):
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 3:
                raise ValueError(f"{path}:{line_number}: expected at least three columns")
            chrom, start, end = fields[0], int(fields[1]), int(fields[2])
            if start < 0 or end <= start:
                raise ValueError(f"{path}:{line_number}: invalid interval")
            if chrom not in eligible_contigs:
                outside += 1
                continue
            if end > eligible_contigs[chrom]:
                raise ValueError(f"{path}:{line_number}: interval exceeds frozen reference")
            identifier = fields[3] if len(fields) > 3 else f"CALL_{len(calls) + 1:06d}"
            signal = float(fields[6]) if len(fields) > 6 and fields[6] not in {"", "."} else 0.0
            calls.append(Call(len(calls), chrom, start, end, identifier, signal))
    calls.sort(key=lambda row: (row.chrom, row.start, row.end, row.identifier, row.index))
    return [Call(index, row.chrom, row.start, row.end, row.identifier, row.signal) for index, row in enumerate(calls)], outside


def intersection(left_start: int, left_end: int, right_start: int, right_end: int) -> int:
    return max(0, min(left_end, right_end) - max(left_start, right_start))


def interval_union(rows) -> dict[str, list[tuple[int, int]]]:
    grouped: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for row in rows:
        grouped[row.chrom].append((row.start, row.end))
    result = {}
    for chrom, intervals in grouped.items():
        merged: list[list[int]] = []
        for start, end in sorted(intervals):
            if not merged or start > merged[-1][1]:
                merged.append([start, end])
            else:
                merged[-1][1] = max(merged[-1][1], end)
        result[chrom] = [(start, end) for start, end in merged]
    return result


def union_length(intervals: dict[str, list[tuple[int, int]]]) -> int:
    return sum(end - start for rows in intervals.values() for start, end in rows)


def union_intersection(left: dict[str, list[tuple[int, int]]], right: dict[str, list[tuple[int, int]]]) -> int:
    total = 0
    for chrom in set(left) & set(right):
        i = j = 0
        while i < len(left[chrom]) and j < len(right[chrom]):
            total += intersection(*left[chrom][i], *right[chrom][j])
            if left[chrom][i][1] <= right[chrom][j][1]:
                i += 1
            else:
                j += 1
    return total


def overlap_graph(truth: list[Domain], calls: list[Call]):
    truth_neighbours: dict[int, list[tuple[int, int]]] = defaultdict(list)
    call_neighbours: dict[int, list[tuple[int, int]]] = defaultdict(list)
    by_chrom_truth: dict[str, list[Domain]] = defaultdict(list)
    by_chrom_calls: dict[str, list[Call]] = defaultdict(list)
    for row in truth:
        by_chrom_truth[row.chrom].append(row)
    for row in calls:
        by_chrom_calls[row.chrom].append(row)
    for chrom, truth_rows in by_chrom_truth.items():
        call_rows = by_chrom_calls[chrom]
        left = 0
        for true in truth_rows:
            while left < len(call_rows) and call_rows[left].end <= true.start:
                left += 1
            cursor = left
            while cursor < len(call_rows) and call_rows[cursor].start < true.end:
                called = call_rows[cursor]
                overlap = intersection(true.start, true.end, called.start, called.end)
                if overlap > 0:
                    truth_neighbours[true.index].append((called.index, overlap))
                    call_neighbours[called.index].append((true.index, overlap))
                cursor += 1
    substantial_truth = {
        true.index: [(call_index, overlap) for call_index, overlap in truth_neighbours[true.index] if overlap >= 500 and overlap / (true.end - true.start) >= 0.10]
        for true in truth
    }
    substantial_call = defaultdict(list)
    for truth_index, neighbours in substantial_truth.items():
        for call_index, overlap in neighbours:
            substantial_call[call_index].append((truth_index, overlap))
    return truth_neighbours, call_neighbours, substantial_truth, dict(substantial_call)


def connected_call_union(calls: list[Call], neighbours: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[list[int]] = []
    for call_index, _overlap in sorted(neighbours, key=lambda row: (calls[row[0]].start, calls[row[0]].end)):
        called = calls[call_index]
        if not merged or called.start > merged[-1][1]:
            merged.append([called.start, called.end])
        else:
            merged[-1][1] = max(merged[-1][1], called.end)
    return [(start, end) for start, end in merged]


def domain_rows(label: str, truth: list[Domain], calls: list[Call]):
    all_truth_edges, _all_call_edges, substantial_truth, substantial_call = overlap_graph(truth, calls)
    rows = []
    for true in truth:
        all_union = connected_call_union(calls, all_truth_edges[true.index])
        substantial_union = connected_call_union(calls, substantial_truth[true.index])
        covered = sum(intersection(true.start, true.end, start, end) for start, end in all_union)
        substantial_intersection = sum(intersection(true.start, true.end, start, end) for start, end in substantial_union)
        substantial_bases = sum(end - start for start, end in substantial_union)
        union_bases = (true.end - true.start) + substantial_bases - substantial_intersection
        degree = len(substantial_truth[true.index])
        merging_involved = any(len(substantial_call.get(call_index, [])) >= 2 for call_index, _ in substantial_truth[true.index])
        simple_call = calls[substantial_truth[true.index][0][0]] if degree == 1 and len(substantial_call.get(substantial_truth[true.index][0][0], [])) == 1 else None
        rows.append({
            "peak_set": label,
            "domain_id": true.domain_id,
            "chrom": true.chrom,
            "start": true.start,
            "end": true.end,
            "width": true.end - true.start,
            "width_class": true.width_class,
            "signal_class": true.signal_class,
            "signal_strength": true.signal_strength,
            "repeat_overlap_bp": true.repeat_overlap_bp,
            "repeat_overlap_fraction": true.repeat_overlap_fraction,
            "coverage_recall": covered / (true.end - true.start),
            "recovered": covered / (true.end - true.start) >= 0.50,
            "per_domain_iou": substantial_intersection / union_bases if union_bases else 0.0,
            "substantial_call_degree": degree,
            "fragmented": degree >= 2,
            "fragmentation_excess": max(0, degree - 1),
            "merging_involved": merging_involved,
            "simple_component": simple_call is not None,
            "left_boundary_signed_bp": simple_call.start - true.start if simple_call else None,
            "right_boundary_signed_bp": simple_call.end - true.end if simple_call else None,
            "left_boundary_absolute_bp": abs(simple_call.start - true.start) if simple_call else None,
            "right_boundary_absolute_bp": abs(simple_call.end - true.end) if simple_call else None,
        })
    return rows, substantial_call


def summarize_domains(label: str, truth: list[Domain], calls: list[Call], outside: int, genome_bases: int):
    rows, substantial_call = domain_rows(label, truth, calls)
    truth_union, call_union = interval_union(truth), interval_union(calls)
    truth_bases, called_bases = union_length(truth_union), union_length(call_union)
    shared = union_intersection(truth_union, call_union)
    union_bases = truth_bases + called_bases - shared
    precision = shared / called_bases if called_bases else None
    recall = shared / truth_bases
    f1 = 2 * precision * recall / (precision + recall) if precision is not None and precision + recall else None
    ious = [row["per_domain_iou"] for row in rows]
    boundary_absolute = [value for row in rows for value in (row["left_boundary_absolute_bp"], row["right_boundary_absolute_bp"]) if value is not None]
    left_signed = [row["left_boundary_signed_bp"] for row in rows if row["left_boundary_signed_bp"] is not None]
    right_signed = [row["right_boundary_signed_bp"] for row in rows if row["right_boundary_signed_bp"] is not None]
    merging_calls = [index for index in range(len(calls)) if len(substantial_call.get(index, [])) >= 2]
    summary = {
        "peak_set": label,
        "called_regions": len(calls),
        "outside_reference_calls": outside,
        "truth_bases": truth_bases,
        "called_bases": called_bases,
        "intersection_bases": shared,
        "union_bases": union_bases,
        "true_negative_bases": genome_bases - union_bases,
        "base_precision": precision,
        "base_recall": recall,
        "base_f1": f1,
        "global_iou": shared / union_bases,
        "recovered_domains": sum(row["recovered"] for row in rows),
        "region_recall": sum(row["recovered"] for row in rows) / len(rows),
        "coverage_recall_mean": statistics.fmean(row["coverage_recall"] for row in rows),
        "per_domain_iou_median": percentile(ious, 0.50),
        "per_domain_iou_p25": percentile(ious, 0.25),
        "per_domain_iou_p75": percentile(ious, 0.75),
        "per_domain_iou_p90": percentile(ious, 0.90),
        "fragmented_domains": sum(row["fragmented"] for row in rows),
        "fragmentation_rate": sum(row["fragmented"] for row in rows) / len(rows),
        "fragmentation_excess": sum(row["fragmentation_excess"] for row in rows),
        "merged_calls": len(merging_calls),
        "merging_rate": len(merging_calls) / len(calls) if calls else None,
        "merging_excess": sum(max(0, len(substantial_call[index]) - 1) for index in merging_calls),
        "truth_domains_in_merges": sum(row["merging_involved"] for row in rows),
        "simple_boundary_components": len(left_signed),
        "boundary_absolute_median_bp": percentile(boundary_absolute, 0.50),
        "boundary_absolute_p90_bp": percentile(boundary_absolute, 0.90),
        "boundary_absolute_p95_bp": percentile(boundary_absolute, 0.95),
        "left_boundary_signed_median_bp": percentile(left_signed, 0.50),
        "right_boundary_signed_median_bp": percentile(right_signed, 0.50),
    }
    return summary, rows


def stratify(label: str, rows: list[dict], columns: tuple[str, ...]) -> list[dict]:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        groups[tuple(row[column] for column in columns)].append(row)
    result = []
    for key, group in sorted(groups.items()):
        boundary = [value for row in group for value in (row["left_boundary_absolute_bp"], row["right_boundary_absolute_bp"]) if value is not None]
        result.append({
            "peak_set": label,
            **dict(zip(columns, key)),
            "truth_domains": len(group),
            "recovered_domains": sum(row["recovered"] for row in group),
            "region_recall": sum(row["recovered"] for row in group) / len(group),
            "coverage_recall_mean": statistics.fmean(row["coverage_recall"] for row in group),
            "per_domain_iou_median": percentile([row["per_domain_iou"] for row in group], 0.50),
            "boundary_absolute_median_bp": percentile(boundary, 0.50),
            "fragmented_domains": sum(row["fragmented"] for row in group),
            "fragmentation_rate": sum(row["fragmented"] for row in group) / len(group),
            "truth_domains_in_merges": sum(row["merging_involved"] for row in group),
            "merge_involvement_rate": sum(row["merging_involved"] for row in group) / len(group),
        })
    return result


def repeat_metrics(label: str, rows: list[dict]) -> list[dict]:
    repeat_values = [row["repeat_overlap_fraction"] for row in rows]
    result = [
        {"peak_set": label, "analysis": "continuous", "group": "all", "n": len(rows), "metric": "coverage_recall", "pearson": pearson(repeat_values, [row["coverage_recall"] for row in rows]), "spearman": spearman(repeat_values, [row["coverage_recall"] for row in rows]), "mean": None, "median": None},
        {"peak_set": label, "analysis": "continuous", "group": "all", "n": len(rows), "metric": "per_domain_iou", "pearson": pearson(repeat_values, [row["per_domain_iou"] for row in rows]), "spearman": spearman(repeat_values, [row["per_domain_iou"] for row in rows]), "mean": None, "median": None},
        {"peak_set": label, "analysis": "continuous", "group": "all", "n": len(rows), "metric": "recovered", "pearson": pearson(repeat_values, [float(row["recovered"]) for row in rows]), "spearman": spearman(repeat_values, [float(row["recovered"]) for row in rows]), "mean": None, "median": None},
    ]
    ordered = sorted(rows, key=lambda row: (row["repeat_overlap_fraction"], row["domain_id"]))
    for quartile in range(4):
        group = ordered[quartile * len(rows) // 4 : (quartile + 1) * len(rows) // 4]
        for metric in ("coverage_recall", "per_domain_iou"):
            values = [row[metric] for row in group]
            result.append({"peak_set": label, "analysis": "quartile", "group": f"Q{quartile + 1}", "n": len(group), "metric": metric, "pearson": None, "spearman": None, "mean": statistics.fmean(values), "median": percentile(values, 0.50)})
        recovered = [float(row["recovered"]) for row in group]
        result.append({"peak_set": label, "analysis": "quartile", "group": f"Q{quartile + 1}", "n": len(group), "metric": "recovered", "pearson": None, "spearman": None, "mean": statistics.fmean(recovered), "median": percentile(recovered, 0.50)})
    return result


def pair_metrics(left_label: str, left: list[Call], right_label: str, right: list[Call]) -> dict:
    left_union, right_union = interval_union(left), interval_union(right)
    left_bases, right_bases = union_length(left_union), union_length(right_union)
    shared = union_intersection(left_union, right_union)
    union_bases = left_bases + right_bases - shared
    return {
        "left": left_label,
        "right": right_label,
        "left_regions": len(left),
        "right_regions": len(right),
        "left_covered_bases": left_bases,
        "right_covered_bases": right_bases,
        "intersection_bases": shared,
        "union_bases": union_bases,
        "base_jaccard": shared / union_bases if union_bases else None,
        "left_reciprocal_overlap": shared / left_bases if left_bases else None,
        "right_reciprocal_overlap": shared / right_bases if right_bases else None,
    }


def assignment(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("peak set must be LABEL=PATH")
    label, path = value.split("=", 1)
    return label, Path(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--truth-strength", required=True, type=Path)
    parser.add_argument("--peak-set", action="append", required=True, type=assignment)
    parser.add_argument("--replicate-pair", action="append", default=[], help="LEFT,RIGHT labels")
    parser.add_argument("--comparison-pair", action="append", default=[], help="LEFT,RIGHT labels")
    parser.add_argument("--primary-label", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    genome_bases = int(config["reference"]["chromosomes"]) * int(config["reference"]["chromosome_length_bp"])
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=False)
    truth = parse_truth(args.truth_strength)
    chromosome_length = int(config["reference"]["chromosome_length_bp"])
    eligible_contigs = {row.chrom: chromosome_length for row in truth}
    summaries, all_domains, width_rows, signal_rows, matrix_rows, repeat_rows = [], [], [], [], [], []
    calls_by_label = {}
    for label, path in args.peak_set:
        calls, outside = parse_calls(path, eligible_contigs)
        summary, domains = summarize_domains(label, truth, calls, outside, genome_bases)
        summaries.append(summary)
        all_domains.extend(domains)
        width_rows.extend(stratify(label, domains, ("width_class",)))
        signal_rows.extend(stratify(label, domains, ("signal_class",)))
        matrix_rows.extend(stratify(label, domains, ("width_class", "signal_class")))
        repeat_rows.extend(repeat_metrics(label, domains))
        calls_by_label[label] = calls
    if args.primary_label not in calls_by_label:
        raise ValueError("primary label not present in peak sets")
    pair_rows = []
    for value in [*args.replicate_pair, *args.comparison_pair]:
        left, right = value.split(",", 1)
        pair_rows.append(pair_metrics(left, calls_by_label[left], right, calls_by_label[right]))

    write_tsv(output / "truth_accuracy.tsv", summaries, list(summaries[0]))
    write_tsv(output / "domain_metrics.tsv", all_domains, list(all_domains[0]))
    write_tsv(output / "width_class_metrics.tsv", width_rows, list(width_rows[0]))
    write_tsv(output / "signal_class_metrics.tsv", signal_rows, list(signal_rows[0]))
    write_tsv(output / "width_signal_metrics.tsv", matrix_rows, list(matrix_rows[0]))
    write_tsv(output / "repeat_overlap_metrics.tsv", repeat_rows, list(repeat_rows[0]))
    write_tsv(output / "replicate_and_external_metrics.tsv", pair_rows, list(pair_rows[0]) if pair_rows else ["left", "right"])

    primary = next(row for row in summaries if row["peak_set"] == args.primary_label)
    primary_signals = {row["signal_class"]: row for row in signal_rows if row["peak_set"] == args.primary_label}
    criteria = {
        "B1": primary_signals["STRONG"]["region_recall"] + 0.05 >= primary_signals["WEAK"]["region_recall"],
        "B2_base_f1": primary["base_f1"] is not None and primary["base_f1"] >= 0.60,
        "B2_median_iou": primary["per_domain_iou_median"] is not None and primary["per_domain_iou_median"] >= 0.40,
        "B3_fragmentation": primary["fragmentation_rate"] <= 0.30,
        "B3_merging": primary["merging_rate"] is not None and primary["merging_rate"] <= 0.30,
        "B4_nonempty": all(row["called_regions"] > 0 for row in summaries),
        "B4_no_summit_assumption": True,
    }
    document = {
        "schema_version": "1.0",
        "type": "synthetic_broad_ground_truth_evaluation",
        "primary_peak_set": args.primary_label,
        "primary_metrics": primary,
        "acceptance_criteria": criteria,
        "acceptance_pass": all(criteria.values()),
        "coordinate_system": "zero-based-half-open",
        "genome_universe_bases": genome_bases,
        "topology": {
            "substantial_minimum_intersection_bp": 500,
            "substantial_minimum_truth_fraction": 0.10,
            "recovered_minimum_truth_coverage": 0.50,
            "per_domain_iou_calls": "union_of_substantially_connected_calls",
            "boundary_components": "one_truth_one_call_in_substantial_graph",
        },
        "repeat_amendment": {
            "interior_traversal": True,
            "exclusion_after_results": False,
            "descriptive_associations": ["coverage_recall", "per_domain_iou", "recovered"],
        },
        "inputs": {
            "config_sha256": sha256(args.config),
            "truth_strength_sha256": sha256(args.truth_strength),
            "peak_sets": {label: {"path": str(path), "sha256": sha256(path)} for label, path in args.peak_set},
        },
    }
    (output / "evaluation_summary.json").write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    checksum_files = sorted(path for path in output.iterdir() if path.is_file())
    (output / "checksums.sha256").write_text("".join(f"{sha256(path)}  {path.name}\n" for path in checksum_files), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
