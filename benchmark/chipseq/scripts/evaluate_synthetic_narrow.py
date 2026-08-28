#!/usr/bin/env python3
"""Evaluate frozen synthetic narrow peak sets without post-hoc choices."""

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
class Peak:
    index: int
    chrom: str
    start: int
    end: int
    identifier: str
    signal: float
    summit: int | None


@dataclass(frozen=True)
class Truth:
    index: int
    peak_id: str
    chrom: str
    start: int
    end: int
    summit: int
    signal_class: str
    strength: float


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_tsv(path: Path, rows: list[dict], columns: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def parse_truth(path: Path) -> list[Truth]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    truth = [
        Truth(
            index=index,
            peak_id=row["peak_id"],
            chrom=row["chrom"],
            start=int(row["start"]),
            end=int(row["end"]),
            summit=int(row["summit"]),
            signal_class=row["signal_class"].upper(),
            strength=float(row["signal_strength"]),
        )
        for index, row in enumerate(rows)
    ]
    if len(truth) != 1500 or len({row.peak_id for row in truth}) != 1500:
        raise ValueError("truth must contain exactly 1,500 unique peaks")
    return truth


def parse_calls(path: Path, eligible_contigs: set[str]) -> tuple[list[Peak], int]:
    calls, outside = [], 0
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip() or line.startswith("#"):
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 10:
                raise ValueError(f"{path}:{line_number}: expected narrowPeak with at least 10 columns")
            chrom, start, end = fields[0], int(fields[1]), int(fields[2])
            if start < 0 or end <= start:
                raise ValueError(f"{path}:{line_number}: invalid interval")
            if chrom not in eligible_contigs:
                outside += 1
                continue
            signal = float(fields[6])
            summit_offset = int(fields[9])
            summit = start + summit_offset if summit_offset >= 0 else None
            calls.append(Peak(len(calls), chrom, start, end, fields[3], signal, summit))
    calls.sort(key=lambda row: (row.chrom, row.start, row.end, row.identifier, row.index))
    return [Peak(index, row.chrom, row.start, row.end, row.identifier, row.signal, row.summit) for index, row in enumerate(calls)], outside


def intersection(left_start: int, left_end: int, right_start: int, right_end: int) -> int:
    return max(0, min(left_end, right_end) - max(left_start, right_start))


def truth_edges(truth: list[Truth], calls: list[Peak]) -> list[tuple[int, int, int, int]]:
    by_chrom_truth: dict[str, list[Truth]] = defaultdict(list)
    by_chrom_calls: dict[str, list[Peak]] = defaultdict(list)
    for row in truth:
        by_chrom_truth[row.chrom].append(row)
    for row in calls:
        by_chrom_calls[row.chrom].append(row)
    edges = []
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
                if overlap >= 100 and overlap / (true.end - true.start) >= 0.25:
                    distance = abs(called.summit - true.summit) if called.summit is not None else 10**9
                    edges.append((true.index, called.index, overlap, distance))
                cursor += 1
    return edges


class FlowEdge:
    def __init__(self, target: int, reverse: int, capacity: int, cost: int):
        self.target, self.reverse, self.capacity, self.cost = target, reverse, capacity, cost


def add_flow_edge(graph: list[list[FlowEdge]], source: int, target: int, capacity: int, cost: int) -> FlowEdge:
    forward = FlowEdge(target, len(graph[target]), capacity, cost)
    reverse = FlowEdge(source, len(graph[source]), 0, -cost)
    graph[source].append(forward)
    graph[target].append(reverse)
    return forward


def deterministic_matching(truth: list[Truth], calls: list[Peak], edges: list[tuple[int, int, int, int]]) -> list[tuple[int, int, int, int]]:
    if not edges:
        return []
    truth_nodes = sorted({edge[0] for edge in edges})
    call_nodes = sorted({edge[1] for edge in edges})
    truth_position = {value: index for index, value in enumerate(truth_nodes)}
    call_position = {value: index for index, value in enumerate(call_nodes)}
    source = 0
    truth_offset = 1
    call_offset = truth_offset + len(truth_nodes)
    sink = call_offset + len(call_nodes)
    graph: list[list[FlowEdge]] = [[] for _ in range(sink + 1)]
    for value in truth_nodes:
        add_flow_edge(graph, source, truth_offset + truth_position[value], 1, 0)
    for value in call_nodes:
        add_flow_edge(graph, call_offset + call_position[value], sink, 1, 0)
    ordered_edges = sorted(edges, key=lambda row: (truth[row[0]].peak_id, calls[row[1]].chrom, calls[row[1]].start, calls[row[1]].end, calls[row[1]].identifier))
    flow_bound = min(len(truth_nodes), len(call_nodes))
    max_distance = max(edge[3] for edge in ordered_edges)
    tie_bound = len(ordered_edges) + 1
    distance_factor = tie_bound * flow_bound + 1
    overlap_factor = (max_distance * distance_factor + tie_bound) * flow_bound + 1
    references = []
    for tie_rank, (truth_index, call_index, overlap, distance) in enumerate(ordered_edges, 1):
        cost = -overlap * overlap_factor + distance * distance_factor + tie_rank
        flow_edge = add_flow_edge(
            graph,
            truth_offset + truth_position[truth_index],
            call_offset + call_position[call_index],
            1,
            cost,
        )
        references.append((truth_index, call_index, overlap, distance, flow_edge))

    while True:
        distance = [None] * len(graph)
        previous: list[tuple[int, int] | None] = [None] * len(graph)
        distance[source] = 0
        queued = [False] * len(graph)
        queue = deque([source])
        queued[source] = True
        while queue:
            node = queue.popleft()
            queued[node] = False
            assert distance[node] is not None
            for edge_index, edge in enumerate(graph[node]):
                if edge.capacity <= 0:
                    continue
                candidate = distance[node] + edge.cost
                if distance[edge.target] is None or candidate < distance[edge.target]:
                    distance[edge.target] = candidate
                    previous[edge.target] = (node, edge_index)
                    if not queued[edge.target]:
                        queue.append(edge.target)
                        queued[edge.target] = True
        if previous[sink] is None:
            break
        node = sink
        while node != source:
            parent, edge_index = previous[node]  # type: ignore[misc]
            edge = graph[parent][edge_index]
            edge.capacity -= 1
            graph[node][edge.reverse].capacity += 1
            node = parent

    matches = [(t, c, overlap, distance) for t, c, overlap, distance, edge in references if edge.capacity == 0]
    matches.sort(key=lambda row: (truth[row[0]].peak_id, calls[row[1]].chrom, calls[row[1]].start, calls[row[1]].end))
    return matches


def percentile(values: list[float], proportion: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * proportion
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] * (upper - position) + ordered[upper] * (position - lower)


def average_ranks(values: list[float]) -> list[float]:
    ordered = sorted(range(len(values)), key=lambda index: (values[index], index))
    ranks = [0.0] * len(values)
    cursor = 0
    while cursor < len(ordered):
        end = cursor + 1
        while end < len(ordered) and values[ordered[end]] == values[ordered[cursor]]:
            end += 1
        rank = (cursor + 1 + end) / 2
        for position in range(cursor, end):
            ranks[ordered[position]] = rank
        cursor = end
    return ranks


def pearson(left: list[float], right: list[float]) -> float | None:
    if len(left) < 2 or len(left) != len(right):
        return None
    left_mean, right_mean = statistics.mean(left), statistics.mean(right)
    numerator = sum((x - left_mean) * (y - right_mean) for x, y in zip(left, right))
    left_ss = sum((x - left_mean) ** 2 for x in left)
    right_ss = sum((y - right_mean) ** 2 for y in right)
    return numerator / math.sqrt(left_ss * right_ss) if left_ss and right_ss else None


def spearman(left: list[float], right: list[float]) -> float | None:
    return pearson(average_ranks(left), average_ranks(right)) if len(left) >= 2 else None


def interval_union(rows: list[Peak]) -> list[tuple[str, int, int]]:
    merged: list[list[object]] = []
    for row in sorted(rows, key=lambda item: (item.chrom, item.start, item.end)):
        if merged and merged[-1][0] == row.chrom and row.start <= int(merged[-1][2]):
            merged[-1][2] = max(int(merged[-1][2]), row.end)
        else:
            merged.append([row.chrom, row.start, row.end])
    return [(str(row[0]), int(row[1]), int(row[2])) for row in merged]


def union_length(rows: list[tuple[str, int, int]]) -> int:
    return sum(end - start for _chrom, start, end in rows)


def union_intersection(left: list[tuple[str, int, int]], right: list[tuple[str, int, int]]) -> int:
    by_left, by_right = defaultdict(list), defaultdict(list)
    for chrom, start, end in left:
        by_left[chrom].append((start, end))
    for chrom, start, end in right:
        by_right[chrom].append((start, end))
    total = 0
    for chrom in set(by_left) & set(by_right):
        i = j = 0
        while i < len(by_left[chrom]) and j < len(by_right[chrom]):
            a, b = by_left[chrom][i], by_right[chrom][j]
            total += intersection(a[0], a[1], b[0], b[1])
            if a[1] <= b[1]:
                i += 1
            else:
                j += 1
    return total


def average_precision(labels: list[int], scores: list[float]) -> tuple[float, list[dict]]:
    total_positive = sum(labels)
    if total_positive == 0:
        raise ValueError("candidate universe has no positives")
    groups: dict[float, list[int]] = defaultdict(list)
    for label, score in zip(labels, scores):
        groups[score].append(label)
    tp = fp = 0
    previous_recall = 0.0
    ap = 0.0
    curve = [{"threshold": "Inf", "precision": 1.0, "recall": 0.0, "tp": 0, "fp": 0}]
    for score in sorted(groups, reverse=True):
        tp += sum(groups[score])
        fp += len(groups[score]) - sum(groups[score])
        recall = tp / total_positive
        precision = tp / (tp + fp)
        ap += (recall - previous_recall) * precision
        previous_recall = recall
        curve.append({"threshold": score, "precision": precision, "recall": recall, "tp": tp, "fp": fp})
    return ap, curve


def candidate_scores(truth: list[Truth], negatives: Path, calls: list[Peak]) -> tuple[list[int], list[float]]:
    windows = []
    for row in truth:
        windows.append((1, row.chrom, max(0, row.summit - 500), row.summit + 500))
    with negatives.open(encoding="utf-8") as handle:
        for line in handle:
            fields = line.rstrip("\n").split("\t")
            start, end = int(fields[1]), int(fields[2])
            center = (start + end) // 2
            windows.append((0, fields[0], max(0, center - 500), center + 500))
    if len(windows) != 3000:
        raise ValueError("candidate universe must contain 1,500 positives and 1,500 negatives")
    by_chrom: dict[str, list[Peak]] = defaultdict(list)
    for call in calls:
        by_chrom[call.chrom].append(call)
    labels, scores = [], []
    for label, chrom, start, end in windows:
        overlapping = [call.signal for call in by_chrom[chrom] if call.start < end and call.end > start]
        labels.append(label)
        scores.append(max(overlapping, default=0.0))
    return labels, scores


def evaluate_peak_set(label: str, path: Path, truth: list[Truth], negatives: Path) -> tuple[dict, list[dict], list[dict], list[dict], list[Peak]]:
    calls, outside = parse_calls(path, {row.chrom for row in truth})
    edges = truth_edges(truth, calls)
    matches = deterministic_matching(truth, calls, edges)
    tp, fp, fn = len(matches), len(calls) - len(matches), len(truth) - len(matches)
    precision = tp / len(calls) if calls else None
    recall = tp / len(truth)
    f1 = 2 * precision * recall / (precision + recall) if precision is not None and precision + recall else None
    fdp = fp / len(calls) if calls else None
    matched_truth = {row[0] for row in matches}
    edge_counts: dict[int, int] = defaultdict(int)
    for truth_index, _call_index, _overlap, _distance in edges:
        edge_counts[truth_index] += 1
    summit_distances = [float(row[3]) for row in matches if calls[row[1]].summit is not None]
    absolute_width_errors = [abs((calls[call_index].end - calls[call_index].start) - 400) for _truth_index, call_index, _overlap, _distance in matches]
    log_width_errors = [math.log2((calls[call_index].end - calls[call_index].start) / 400) for _truth_index, call_index, _overlap, _distance in matches]
    strength = [truth[truth_index].strength for truth_index, _call_index, _overlap, _distance in matches]
    called_signal = [calls[call_index].signal for _truth_index, call_index, _overlap, _distance in matches]
    labels, scores = candidate_scores(truth, negatives, calls)
    auprc, curve = average_precision(labels, scores)
    class_rows = []
    for signal_class in ("STRONG", "MEDIUM", "WEAK"):
        class_truth = [row for row in truth if row.signal_class == signal_class]
        class_matches = [row for row in matches if truth[row[0]].signal_class == signal_class]
        class_distances = [float(row[3]) for row in class_matches if calls[row[1]].summit is not None]
        class_signals = [calls[row[1]].signal for row in class_matches]
        class_rows.append({
            "peak_set": label, "signal_class": signal_class, "truth": len(class_truth), "recovered": len(class_matches),
            "recall": len(class_matches) / len(class_truth),
            "median_summit_distance_bp": percentile(class_distances, 0.5),
            "median_called_signal": percentile(class_signals, 0.5),
        })
    match_rows = []
    for truth_index, call_index, overlap, distance in matches:
        true, called = truth[truth_index], calls[call_index]
        match_rows.append({
            "peak_set": label, "peak_id": true.peak_id, "signal_class": true.signal_class, "true_strength": true.strength,
            "truth_chrom": true.chrom, "truth_start": true.start, "truth_end": true.end, "truth_summit": true.summit,
            "call_id": called.identifier, "call_start": called.start, "call_end": called.end, "call_summit": called.summit,
            "called_signal": called.signal, "intersection_bp": overlap, "summit_distance_bp": distance,
            "absolute_width_error_bp": abs((called.end - called.start) - 400),
            "log2_width_ratio": math.log2((called.end - called.start) / 400),
        })
    summary = {
        "peak_set": label, "path": str(path), "sha256": sha256(path), "called_peaks": len(calls), "outside_eligible_contigs_removed": outside,
        "tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": f1, "observed_fdp": fdp,
        "candidate_auprc": auprc, "candidate_prevalence": 0.5, "candidate_zero_score_fraction": scores.count(0.0) / len(scores),
        "summit_mean_bp": statistics.mean(summit_distances) if summit_distances else None,
        "summit_median_bp": percentile(summit_distances, 0.5), "summit_p90_bp": percentile(summit_distances, 0.9),
        "summit_p95_bp": percentile(summit_distances, 0.95), "summit_iqr_bp": (percentile(summit_distances, 0.75) - percentile(summit_distances, 0.25)) if summit_distances else None,
        "median_absolute_width_error_bp": percentile([float(value) for value in absolute_width_errors], 0.5),
        "median_log2_width_ratio": percentile(log_width_errors, 0.5), "truth_signal_called_rank_spearman": spearman(strength, called_signal),
        "fragmented_truth": sum(count > 1 for count in edge_counts.values()),
        "fragmentation_rate": sum(count > 1 for count in edge_counts.values()) / len(truth),
        "matched_truth": len(matched_truth),
    }
    curve_rows = [{"peak_set": label, **row} for row in curve]
    return summary, class_rows, match_rows, curve_rows, calls


def replicate_metrics(left_label: str, left: list[Peak], right_label: str, right: list[Peak]) -> dict:
    left_union, right_union = interval_union(left), interval_union(right)
    shared = union_intersection(left_union, right_union)
    left_bases, right_bases = union_length(left_union), union_length(right_union)
    union_bases = left_bases + right_bases - shared
    pseudo_truth = [Truth(row.index, row.identifier, row.chrom, row.start, row.end, row.summit or row.start, "REPLICATE", row.signal) for row in left]
    edges = []
    by_chrom = defaultdict(list)
    for row in right:
        by_chrom[row.chrom].append(row)
    for row in left:
        for called in by_chrom[row.chrom]:
            overlap = intersection(row.start, row.end, called.start, called.end)
            if overlap > 0:
                distance = abs((row.summit or row.start) - (called.summit or called.start))
                edges.append((row.index, called.index, overlap, distance))
    matches = deterministic_matching(pseudo_truth, right, edges)
    left_signal = [left[t].signal for t, _c, _o, _d in matches]
    right_signal = [right[c].signal for _t, c, _o, _d in matches]
    return {
        "left": left_label, "right": right_label, "left_peaks": len(left), "right_peaks": len(right),
        "intersection_bases": shared, "union_bases": union_bases,
        "base_jaccard": shared / union_bases if union_bases else None,
        "left_reciprocal_overlap": shared / left_bases if left_bases else None,
        "right_reciprocal_overlap": shared / right_bases if right_bases else None,
        "one_to_one_matches": len(matches), "rank_spearman": spearman(left_signal, right_signal),
    }


def parse_assignment(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("peak set must be LABEL=PATH")
    label, path = value.split("=", 1)
    return label, Path(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--truth-strength", required=True, type=Path)
    parser.add_argument("--negative-bed", required=True, type=Path)
    parser.add_argument("--peak-set", action="append", required=True, type=parse_assignment)
    parser.add_argument("--replicate-pair", action="append", default=[], help="LEFT,RIGHT labels")
    parser.add_argument("--primary-label", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=False)
    truth = parse_truth(args.truth_strength)
    summaries, classes, matches, curves, calls_by_label = [], [], [], [], {}
    for label, path in args.peak_set:
        summary, class_rows, match_rows, curve_rows, calls = evaluate_peak_set(label, path, truth, args.negative_bed)
        summaries.append(summary)
        classes.extend(class_rows)
        matches.extend(match_rows)
        curves.extend(curve_rows)
        calls_by_label[label] = calls
    if args.primary_label not in calls_by_label:
        raise ValueError("primary label not present in peak sets")
    replicate_rows = []
    for value in args.replicate_pair:
        left, right = value.split(",", 1)
        replicate_rows.append(replicate_metrics(left, calls_by_label[left], right, calls_by_label[right]))

    metric_columns = list(summaries[0])
    write_tsv(output / "truth_accuracy.tsv", summaries, metric_columns)
    write_tsv(output / "signal_class_metrics.tsv", classes, list(classes[0]))
    write_tsv(output / "matched_peaks.tsv", matches, list(matches[0]) if matches else ["peak_set", "peak_id"])
    write_tsv(output / "precision_recall_curve.tsv", curves, list(curves[0]))
    write_tsv(output / "replicate_metrics.tsv", replicate_rows, list(replicate_rows[0]) if replicate_rows else ["left", "right"])
    primary = next(row for row in summaries if row["peak_set"] == args.primary_label)
    by_class = {row["signal_class"]: row for row in classes if row["peak_set"] == args.primary_label}
    criteria = {
        "N1": by_class["STRONG"]["recall"] + 0.05 >= by_class["WEAK"]["recall"],
        "N2_f1": primary["f1"] is not None and primary["f1"] >= 0.70,
        "N2_strong_recall": by_class["STRONG"]["recall"] >= 0.80,
        "N3_summit": primary["summit_median_bp"] is not None and primary["summit_median_bp"] <= 100,
        "N3_fdp": primary["observed_fdp"] is not None and primary["observed_fdp"] <= 0.25,
        "N4_nonempty": all(row["called_peaks"] > 0 for row in summaries),
    }
    document = {
        "schema_version": "1.0", "type": "synthetic_narrow_ground_truth_evaluation",
        "primary_peak_set": args.primary_label, "primary_metrics": primary,
        "acceptance_criteria": criteria, "acceptance_pass": all(criteria.values()),
        "coordinate_system": "zero-based-half-open", "matching": {
            "minimum_intersection_bp": 100, "minimum_truth_fraction": 0.25,
            "objective": ["maximum_cardinality", "maximum_total_intersection", "minimum_total_summit_distance", "deterministic_tie_order"],
        },
        "candidate_auprc": {"positives": 1500, "negatives": 1500, "window_bp": 1000, "score": "maximum_overlapping_MACS3_signalValue_or_zero", "prevalence": 0.5},
        "inputs": {"truth_strength_sha256": sha256(args.truth_strength), "negative_bed_sha256": sha256(args.negative_bed)},
    }
    (output / "evaluation_summary.json").write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    checksum_files = sorted(path for path in output.iterdir() if path.is_file())
    (output / "checksums.sha256").write_text("".join(f"{sha256(path)}  {path.name}\n" for path in checksum_files), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
