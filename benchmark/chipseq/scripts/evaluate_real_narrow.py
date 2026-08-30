#!/usr/bin/env python3
"""Evaluate the frozen K562 CTCF Real Narrow benchmark without tuning."""

from __future__ import annotations

import argparse
import bisect
import csv
import gzip
import hashlib
import json
import math
import os
import random
import shutil
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import mannwhitneyu, spearmanr


SCHEMA_VERSION = "1.0"
CONTROL_SEED = 20261001
NULL_SEED = 20261002
NULL_SETS = 100
NULL_CANDIDATES = 2000
GC_TOLERANCE = 0.005
MIN_POOL_SIZE = 200
POOL_MULTIPLIER = 20
MAX_POOL_ATTEMPT_MULTIPLIER = 10000
RN3_INFERENCE_LOCKED = True


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def read_peaks(path: Path, require_summit: bool = True) -> list[dict[str, object]]:
    opener = gzip.open if path.suffix == ".gz" else Path.open
    kwargs = {"mode": "rt", "encoding": "utf-8"} if path.suffix == ".gz" else {"mode": "r", "encoding": "utf-8"}
    peaks = []
    with opener(path, **kwargs) as handle:
        for number, line in enumerate(handle, start=1):
            if not line.strip() or line.startswith(("#", "track", "browser")):
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 10:
                raise ValueError(f"invalid narrowPeak row {number}: {path}")
            start, end, summit_offset = int(fields[1]), int(fields[2]), int(float(fields[9]))
            if start < 0 or end <= start:
                raise ValueError(f"invalid narrowPeak coordinates at row {number}: {path}")
            summit_valid = 0 <= summit_offset < end - start
            if require_summit and not summit_valid:
                raise ValueError(f"invalid narrowPeak summit at row {number}: {path}")
            peaks.append({
                "chrom": fields[0], "start": start, "end": end, "name": fields[3],
                "signal": float(fields[6]),
                "summit": start + summit_offset if summit_valid else None,
                "fields": fields,
            })
    if not peaks:
        raise ValueError(f"empty peak file: {path}")
    return peaks


def group_intervals(peaks: list[dict[str, object]]) -> dict[str, list[tuple[int, int]]]:
    grouped: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for peak in peaks:
        grouped[str(peak["chrom"])].append((int(peak["start"]), int(peak["end"])))
    return {chrom: sorted(values) for chrom, values in grouped.items()}


def merge_intervals(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[list[int]] = []
    for start, end in sorted(intervals):
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return [(start, end) for start, end in merged]


def union_by_chrom(peaks: list[dict[str, object]], allowed: set[str] | None = None) -> dict[str, list[tuple[int, int]]]:
    grouped = group_intervals([peak for peak in peaks if allowed is None or peak["chrom"] in allowed])
    return {chrom: merge_intervals(values) for chrom, values in grouped.items()}


def total_length(grouped: dict[str, list[tuple[int, int]]]) -> int:
    return sum(end - start for intervals in grouped.values() for start, end in intervals)


def intersection_length(
    left: dict[str, list[tuple[int, int]]], right: dict[str, list[tuple[int, int]]]
) -> int:
    total = 0
    for chrom in left.keys() & right.keys():
        a, b, i, j = left[chrom], right[chrom], 0, 0
        while i < len(a) and j < len(b):
            total += max(0, min(a[i][1], b[j][1]) - max(a[i][0], b[j][0]))
            if a[i][1] <= b[j][1]:
                i += 1
            else:
                j += 1
    return total


def gc_decile(gc_bases: int, valid_bases: int) -> int:
    """Return [0, 9] for [0, 0.1), ..., [0.9, 1.0]."""
    if valid_bases <= 0:
        raise ValueError("GC class requires at least one valid A/C/G/T base")
    return min(9, (10 * gc_bases) // valid_bases)


def sample_gc_conditioned(
    pool: list[tuple[int, int]], target_gc_bases: list[int], rng: random.Random
) -> list[tuple[int, int]]:
    """Sample distinct positions while matching target GC counts within a class."""
    available: dict[int, list[int]] = defaultdict(list)
    for start, gc_bases in pool:
        available[gc_bases].append(start)
    for starts in available.values():
        rng.shuffle(starts)
    targets = list(target_gc_bases)
    rng.shuffle(targets)
    selected = []
    for target in targets:
        populated = [gc_bases for gc_bases, starts in available.items() if starts]
        distance = min(abs(gc_bases - target) for gc_bases in populated)
        nearest = [gc_bases for gc_bases in populated if abs(gc_bases - target) == distance]
        selected_gc = rng.choice(nearest)
        selected.append((available[selected_gc].pop(), selected_gc))
    return selected


def interval_overlaps(merged: list[tuple[int, int]], starts: list[int], start: int, end: int) -> bool:
    index = bisect.bisect_left(starts, end) - 1
    return index >= 0 and merged[index][1] > start


def semantic_equal(left: list[dict[str, object]], right: list[dict[str, object]]) -> bool:
    if len(left) != len(right):
        return False
    for first, second in zip(left, right):
        left_fields, right_fields = list(first["fields"]), list(second["fields"])
        left_fields[3] = right_fields[3] = "."
        if left_fields != right_fields:
            return False
    return True


def replicate_matches(left: list[dict[str, object]], right: list[dict[str, object]]) -> list[tuple[dict, dict, int]]:
    by_left, by_right = defaultdict(list), defaultdict(list)
    for peak in left:
        by_left[peak["chrom"]].append(peak)
    for peak in right:
        by_right[peak["chrom"]].append(peak)
    candidates = []
    for chrom in by_left.keys() & by_right.keys():
        first, second = sorted(by_left[chrom], key=lambda p: p["start"]), sorted(by_right[chrom], key=lambda p: p["start"])
        j = 0
        for li, lp in enumerate(first):
            while j < len(second) and second[j]["end"] <= lp["start"]:
                j += 1
            k = j
            while k < len(second) and second[k]["start"] < lp["end"]:
                overlap = min(lp["end"], second[k]["end"]) - max(lp["start"], second[k]["start"])
                if overlap > 0:
                    candidates.append((-overlap, abs(lp["summit"] - second[k]["summit"]), chrom, li, k, lp, second[k]))
                k += 1
    matches, used_left, used_right = [], set(), set()
    for neg_overlap, _distance, chrom, li, ri, lp, rp in sorted(candidates, key=lambda row: row[:5]):
        left_key, right_key = (chrom, li), (chrom, ri)
        if left_key in used_left or right_key in used_right:
            continue
        used_left.add(left_key)
        used_right.add(right_key)
        matches.append((lp, rp, -neg_overlap))
    return matches


class FastaReader:
    def __init__(self, fasta: Path, fai: Path):
        self.fasta = fasta
        self.index = {}
        for line in fai.read_text(encoding="ascii").splitlines():
            chrom, length, offset, line_bases, line_width = line.split("\t")[:5]
            self.index[chrom] = tuple(map(int, (length, offset, line_bases, line_width)))

    def read_chrom(self, chrom: str) -> bytes:
        length, offset, line_bases, line_width = self.index[chrom]
        raw_bytes = length + math.ceil(length / line_bases) * (line_width - line_bases) + line_width
        with self.fasta.open("rb") as handle:
            handle.seek(offset)
            sequence = handle.read(raw_bytes).replace(b"\n", b"").replace(b"\r", b"")[:length].upper()
        if len(sequence) != length:
            raise ValueError(f"failed to read complete FASTA contig {chrom}")
        return sequence


def parse_jaspar(path: Path) -> np.ndarray:
    rows = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith(">"):
            continue
        base = line[0].upper()
        values = [float(value) for value in line.split("[", 1)[1].split("]", 1)[0].split()]
        rows[base] = values
    if set(rows) != set("ACGT") or len({len(values) for values in rows.values()}) != 1:
        raise ValueError("invalid JASPAR matrix")
    counts = np.asarray([rows[base] for base in "ACGT"], dtype=np.float64).T
    probabilities = (counts + 0.8) / (counts.sum(axis=1, keepdims=True) + 3.2)
    return np.log2(probabilities / 0.25)


def pwm_max_scores(windows: list[bytes], pwm: np.ndarray, batch_size: int = 1000) -> tuple[np.ndarray, np.ndarray]:
    lookup = np.full(256, -1, dtype=np.int8)
    for index, base in enumerate(b"ACGT"):
        lookup[base] = index
    motif_width = pwm.shape[0]
    reverse = pwm[::-1][:, [3, 2, 1, 0]]
    all_scores, all_centers = [], []
    for offset in range(0, len(windows), batch_size):
        batch = windows[offset:offset + batch_size]
        width = len(batch[0])
        encoded = lookup[np.frombuffer(b"".join(batch), dtype=np.uint8).reshape(len(batch), width)]
        if np.any(encoded < 0):
            raise ValueError("motif window contains a non-ACGT base")
        positions = width - motif_width + 1
        forward = np.zeros((len(batch), positions), dtype=np.float64)
        backward = np.zeros_like(forward)
        for column in range(motif_width):
            bases = encoded[:, column:column + positions]
            forward += pwm[column][bases]
            backward += reverse[column][bases]
        combined = np.maximum(forward, backward)
        best = np.argmax(combined, axis=1)
        all_scores.append(combined[np.arange(len(batch)), best])
        all_centers.append(best + motif_width / 2.0)
    return np.concatenate(all_scores), np.concatenate(all_centers)


def annotation_distribution(gtf_gz: Path, peaks: list[dict[str, object]]) -> dict[str, int]:
    promoters, exons, genes = defaultdict(list), defaultdict(list), defaultdict(list)
    with gzip.open(gtf_gz, "rt", encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("#"):
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) != 9 or fields[2] not in {"gene", "exon"}:
                continue
            chrom, start, end = fields[0], int(fields[3]) - 1, int(fields[4])
            if fields[2] == "exon":
                exons[chrom].append((start, end))
            else:
                genes[chrom].append((start, end))
                if fields[6] == "+":
                    promoters[chrom].append((max(0, start - 2000), start + 500))
                else:
                    promoters[chrom].append((max(0, end - 500), end + 2000))
    merged = {name: {chrom: merge_intervals(values) for chrom, values in source.items()}
              for name, source in (("promoter", promoters), ("exon", exons), ("gene_body", genes))}
    starts = {name: {chrom: [start for start, _ in values] for chrom, values in source.items()}
              for name, source in merged.items()}
    counts = {"promoter": 0, "exon": 0, "intron_or_gene_body": 0, "intergenic": 0}
    for peak in peaks:
        chrom, start, end = str(peak["chrom"]), int(peak["start"]), int(peak["end"])
        if chrom in merged["promoter"] and interval_overlaps(merged["promoter"][chrom], starts["promoter"][chrom], start, end):
            counts["promoter"] += 1
        elif chrom in merged["exon"] and interval_overlaps(merged["exon"][chrom], starts["exon"][chrom], start, end):
            counts["exon"] += 1
        elif chrom in merged["gene_body"] and interval_overlaps(merged["gene_body"][chrom], starts["gene_body"][chrom], start, end):
            counts["intron_or_gene_body"] += 1
        else:
            counts["intergenic"] += 1
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    if "SLURM_JOB_ID" not in os.environ:
        raise RuntimeError("evaluation must run in a Slurm allocation")
    if RN3_INFERENCE_LOCKED:
        raise RuntimeError(
            "RN3 inference is locked until two validated null-generator runs "
            "produce byte-identical frozen null sets"
        )
    root = args.benchmark_root.resolve()
    expected = Path("/scratch/Schisto-epigenetics/gustavo/helixforge-chipseq-real-narrow-benchmark-20260830")
    if root != expected or args.output_dir.exists():
        raise ValueError("unexpected benchmark root or existing evaluation output")

    hf_results = root / "helixforge/results"
    hf_r1_path = hf_results / "080-peak-calling/ENCFF000BWM.CTCF.narrow.macs3.peak_calling/peaks.narrowPeak"
    hf_r2_path = hf_results / "080-peak-calling/ENCFF000BWR.CTCF.narrow.macs3.peak_calling/peaks.narrowPeak"
    hf_idr_path = next((hf_results / "chipseq/consensus").glob("*/*/idr_output.narrowPeak"))
    ind = root / "independent"
    ind_r1_path = ind / "peaks/ENCFF000BWM/ENCFF000BWM_peaks.narrowPeak"
    ind_r2_path = ind / "peaks/ENCFF000BWR/ENCFF000BWR_peaks.narrowPeak"
    ind_idr_path = ind / "idr/idr_output.narrowPeak"
    external_path = root / "downloads/external/ENCFF519CXF.bed.gz"
    fasta_path, fai_path = root / "reference/genome.fa", root / "reference/genome.fa.fai"
    blacklist_path = root / "reference/blacklist.bed"
    motif_path = root / "downloads/motif/MA0139.1.jaspar"
    gtf_gz = root / "downloads/reference/gencode.v50.primary_assembly.annotation.gtf.gz"

    hf_r1, hf_r2, hf_idr = map(read_peaks, (hf_r1_path, hf_r2_path, hf_idr_path))
    ind_r1, ind_r2, ind_idr = map(read_peaks, (ind_r1_path, ind_r2_path, ind_idr_path))
    external = read_peaks(external_path, require_summit=False)
    reference_manifest = json.loads((root / "reference/reference_manifest.json").read_text(encoding="utf-8"))
    fasta = FastaReader(fasta_path, fai_path)
    shared = set(fasta.index) & {str(peak["chrom"]) for peak in external}
    lengths = {chrom: fasta.index[chrom][0] for chrom in shared}
    comparison_idr = [peak for peak in hf_idr if peak["chrom"] in shared]
    external_shared = [peak for peak in external if peak["chrom"] in shared]

    r1_semantic, r2_semantic = semantic_equal(hf_r1, ind_r1), semantic_equal(hf_r2, ind_r2)
    idr_exact = sha256(hf_idr_path) == sha256(ind_idr_path)
    matches = replicate_matches(hf_r1, hf_r2)
    rank = spearmanr([pair[0]["signal"] for pair in matches], [pair[1]["signal"] for pair in matches]).statistic
    r1_union, r2_union = union_by_chrom(hf_r1), union_by_chrom(hf_r2)
    replicate_intersection = intersection_length(r1_union, r2_union)
    replicate_union = total_length(r1_union) + total_length(r2_union) - replicate_intersection

    observed_union, encode_union = union_by_chrom(comparison_idr), union_by_chrom(external_shared)
    observed_overlap = intersection_length(observed_union, encode_union)
    observed_jaccard = observed_overlap / (total_length(observed_union) + total_length(encode_union) - observed_overlap)

    sorted_chroms = sorted(shared)
    original_gc = original_valid = 0
    null_rng = random.Random(NULL_SEED)
    relocation_groups: list[dict[str, object]] = []
    capacity_rows: list[dict[str, object]] = []
    motif_rng = random.Random(CONTROL_SEED)
    pwm = parse_jaspar(motif_path)
    motif_peak_scores, motif_control_scores, motif_peak_centers = [], [], []
    # Parse the blacklist directly; it has no summit columns.
    blacklist_intervals: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for line in blacklist_path.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            chrom, start, end = line.split("\t")[:3]
            blacklist_intervals[chrom].append((int(start), int(end)))
    blacklist_merged = {chrom: merge_intervals(values) for chrom, values in blacklist_intervals.items()}

    peaks_by_chrom = defaultdict(list)
    for peak in comparison_idr:
        peaks_by_chrom[str(peak["chrom"])].append(peak)
    for chrom in sorted_chroms:
        sequence = fasta.read_chrom(chrom)
        encoded = np.frombuffer(sequence, dtype=np.uint8)
        valid = np.isin(encoded, np.frombuffer(b"ACGT", dtype=np.uint8))
        gc = (encoded == ord("G")) | (encoded == ord("C"))
        valid_prefix = np.concatenate((np.zeros(1, dtype=np.uint64), np.cumsum(valid, dtype=np.uint64)))
        gc_prefix = np.concatenate((np.zeros(1, dtype=np.uint64), np.cumsum(gc, dtype=np.uint64)))
        chrom_peaks = peaks_by_chrom.get(chrom, [])
        if chrom_peaks:
            starts = np.asarray([peak["start"] for peak in chrom_peaks], dtype=np.int64)
            ends = np.asarray([peak["end"] for peak in chrom_peaks], dtype=np.int64)
            widths = ends - starts
            peak_gc = gc_prefix[ends] - gc_prefix[starts]
            peak_valid = valid_prefix[ends] - valid_prefix[starts]
            if np.any(peak_valid != widths):
                raise ValueError(f"observed peak contains non-ACGT bases on {chrom}")
            original_gc += int(np.sum(peak_gc))
            original_valid += int(np.sum(peak_valid))

            grouped_peaks: dict[tuple[int, int], list[tuple[dict[str, object], int]]] = defaultdict(list)
            for peak, width, gc_bases, valid_bases in zip(chrom_peaks, widths, peak_gc, peak_valid):
                grouped_peaks[(int(width), gc_decile(int(gc_bases), int(valid_bases)))].append(
                    (peak, int(gc_bases))
                )

            blacklist_for_chrom = blacklist_merged.get(chrom, [])
            blacklist_starts = [start for start, _ in blacklist_for_chrom]
            for (width, gc_class), group_records in sorted(grouped_peaks.items()):
                group_peaks = [record[0] for record in group_records]
                target_gc_bases = [record[1] for record in group_records]
                pool_target = max(MIN_POOL_SIZE, POOL_MULTIPLIER * len(group_records))
                max_attempts = max(10000, MAX_POOL_ATTEMPT_MULTIPLIER * pool_target)
                candidates: dict[int, int] = {}
                attempts = 0
                while len(candidates) < pool_target and attempts < max_attempts:
                    attempts += 1
                    candidate_start = null_rng.randrange(0, lengths[chrom] - width + 1)
                    if candidate_start in candidates:
                        continue
                    candidate_end = candidate_start + width
                    if interval_overlaps(
                        blacklist_for_chrom, blacklist_starts, candidate_start, candidate_end
                    ):
                        continue
                    valid_bases = int(valid_prefix[candidate_end] - valid_prefix[candidate_start])
                    if valid_bases != width:
                        continue
                    gc_bases = int(gc_prefix[candidate_end] - gc_prefix[candidate_start])
                    if gc_decile(gc_bases, valid_bases) != gc_class:
                        continue
                    candidates[candidate_start] = gc_bases
                if len(candidates) < pool_target:
                    raise RuntimeError(
                        f"null relocation capacity failed for {chrom}, width={width}, "
                        f"GC decile={gc_class}: {len(candidates)}/{pool_target} candidates "
                        f"after {attempts} probes"
                    )
                pool = sorted(candidates.items())
                relocation_groups.append({
                    "chrom": chrom,
                    "width": width,
                    "gc_class": gc_class,
                    "peaks": group_peaks,
                    "target_gc_bases": target_gc_bases,
                    "pool": pool,
                })
                capacity_rows.append({
                    "chrom": chrom,
                    "width": width,
                    "gc_class": gc_class,
                    "observed_peaks": len(group_peaks),
                    "required_per_null_set": len(group_peaks),
                    "candidate_pool": len(pool),
                    "capacity_ratio": len(pool) / len(group_peaks),
                    "random_probes": attempts,
                })

        excluded = merge_intervals(group_intervals(comparison_idr).get(chrom, []) + blacklist_merged.get(chrom, []))
        excluded_starts = [start for start, _ in excluded]
        peak_windows, control_windows = [], []
        for peak in chrom_peaks:
            start, end = int(peak["summit"]) - 100, int(peak["summit"]) + 100
            if start < 0 or end > len(sequence):
                raise ValueError(f"summit window outside reference: {peak['name']}")
            window = sequence[start:end]
            if any(base not in b"ACGT" for base in window):
                raise ValueError(f"summit window contains non-ACGT bases: {peak['name']}")
            peak_windows.append(window)
            window_gc_decile = gc_decile(
                window.count(b"G") + window.count(b"C"), len(window)
            )
            selected = 0
            for _attempt in range(100000):
                candidate_start = motif_rng.randrange(0, len(sequence) - len(window) + 1)
                candidate_end = candidate_start + len(window)
                if interval_overlaps(excluded, excluded_starts, candidate_start, candidate_end):
                    continue
                candidate = sequence[candidate_start:candidate_end]
                if any(base not in b"ACGT" for base in candidate):
                    continue
                candidate_decile = gc_decile(
                    candidate.count(b"G") + candidate.count(b"C"), len(candidate)
                )
                if candidate_decile != window_gc_decile:
                    continue
                control_windows.append(candidate)
                selected += 1
                if selected == 10:
                    break
            if selected != 10:
                raise RuntimeError(f"failed to generate ten matched controls for {peak['name']}")
        if peak_windows:
            peak_scores, peak_centers = pwm_max_scores(peak_windows, pwm)
            control_scores, _ = pwm_max_scores(control_windows, pwm)
            motif_peak_scores.extend(peak_scores.tolist())
            motif_peak_centers.extend(peak_centers.tolist())
            motif_control_scores.extend(control_scores.tolist())

    original_fraction = original_gc / original_valid
    accepted_sets: list[dict[str, object]] = []
    relocation_reuse: Counter[tuple[str, int, int]] = Counter()
    for candidate_index in range(1, NULL_CANDIDATES + 1):
        grouped: dict[str, list[tuple[int, int]]] = defaultdict(list)
        candidate_gc = 0
        candidate_valid = 0
        selected_keys = []
        for group in relocation_groups:
            chrom = str(group["chrom"])
            width = int(group["width"])
            selected = sample_gc_conditioned(
                group["pool"], group["target_gc_bases"], null_rng
            )
            for start, gc_bases in selected:
                end = int(start) + width
                grouped[chrom].append((int(start), end))
                candidate_gc += int(gc_bases)
                candidate_valid += width
                selected_keys.append((chrom, int(start), end))
        candidate_fraction = candidate_gc / candidate_valid
        if abs(candidate_fraction - original_fraction) <= GC_TOLERANCE:
            for key in selected_keys:
                relocation_reuse[key] += 1
            accepted_sets.append({
                "candidate_index": candidate_index,
                "gc_fraction": candidate_fraction,
                "intervals": {chrom: merge_intervals(values) for chrom, values in grouped.items()},
            })
            if len(accepted_sets) == NULL_SETS:
                break
    if len(accepted_sets) != NULL_SETS:
        raise RuntimeError(
            f"only {len(accepted_sets)} of {NULL_CANDIDATES} matched relocations met "
            f"aggregate GC tolerance; observed={original_fraction:.6f}"
        )
    null_rows = []
    null_exceed = 0
    for null_index, accepted in enumerate(accepted_sets, start=1):
        relocated = accepted["intervals"]
        overlap = intersection_length(relocated, encode_union)
        jaccard = overlap / (total_length(relocated) + total_length(encode_union) - overlap)
        null_exceed += int(overlap >= observed_overlap)
        null_rows.append({
            "null_id": null_index, "candidate_index": int(accepted["candidate_index"]),
            "gc_fraction": float(accepted["gc_fraction"]),
            "gc_absolute_difference": float(abs(accepted["gc_fraction"] - original_fraction)),
            "overlap_bp": overlap, "jaccard": jaccard,
        })
    empirical_p = (1 + null_exceed) / 101

    motif_test = mannwhitneyu(motif_peak_scores, motif_control_scores, alternative="greater")
    motif_width = pwm.shape[0]
    central = sum(abs(center - 100) <= 25 for center in motif_peak_centers)
    annotations = annotation_distribution(gtf_gz, comparison_idr)
    metrics = {
        "implementation": {
            "replicate_1_semantic_equal": r1_semantic,
            "replicate_2_semantic_equal": r2_semantic,
            "idr_byte_identical": idr_exact,
        },
        "counts": {"replicate_1": len(hf_r1), "replicate_2": len(hf_r2), "idr": len(hf_idr)},
        "replicates": {
            "matched_peaks": len(matches), "rank_spearman": float(rank),
            "base_intersection_bp": replicate_intersection,
            "base_jaccard": replicate_intersection / replicate_union,
        },
        "encode_overlap": {
            "shared_contigs": len(shared), "observed_overlap_bp": observed_overlap,
            "observed_jaccard": observed_jaccard, "idr_gc_fraction": original_fraction,
            "null_sets": NULL_SETS, "null_exceedances": null_exceed, "empirical_p": empirical_p,
            "null_method": "chromosome-, width-, and GC-decile-matched independent relocation",
            "gc_deciles": "[0.0,0.1),...,[0.9,1.0]",
            "aggregate_gc_tolerance": GC_TOLERANCE,
            "candidate_sets_examined": int(accepted_sets[-1]["candidate_index"]),
            "minimum_pool_capacity_ratio": min(row["capacity_ratio"] for row in capacity_rows),
            "unique_relocated_intervals": len(relocation_reuse),
            "maximum_interval_reuse": max(relocation_reuse.values()),
        },
        "motif": {
            "matrix_id": "MA0139.1", "peak_windows": len(motif_peak_scores),
            "control_windows": len(motif_control_scores), "controls_per_peak": 10,
            "peak_score_median": float(np.median(motif_peak_scores)),
            "control_score_median": float(np.median(motif_control_scores)),
            "mann_whitney_u": float(motif_test.statistic), "p_value": float(motif_test.pvalue),
            "bh_adjusted_p": float(motif_test.pvalue),
            "central_window_fraction": central / len(motif_peak_centers),
        },
        "annotation_distribution": annotations,
    }
    criteria = {
        "RN1": {"type": "RELEASE_GATE", "pass": all((len(hf_r1), len(hf_r2), len(hf_idr), r1_semantic, r2_semantic, idr_exact))},
        "RN2": {"type": "SANITY_CHECK", "pass": bool(motif_test.pvalue < 0.05), "value": float(motif_test.pvalue)},
        "RN3": {"type": "EXPECTED_RANGE", "pass": empirical_p <= 0.01, "value": empirical_p},
        "RN4": {"type": "EXPECTED_RANGE", "pass": bool(rank > 0 and len(hf_idr) > 0), "value": float(rank)},
        "RN5": {"type": "DESCRIPTIVE", "pass": None},
    }

    args.output_dir.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".real-narrow-evaluation.", dir=args.output_dir.parent))
    try:
        (stage / "metrics.json").write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (stage / "criteria.json").write_text(json.dumps(criteria, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        with (stage / "null_overlap.tsv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(null_rows[0]), delimiter="\t", lineterminator="\n")
            writer.writeheader(); writer.writerows(null_rows)
        with (stage / "null_relocation_capacity.tsv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(capacity_rows[0]), delimiter="\t", lineterminator="\n")
            writer.writeheader(); writer.writerows(capacity_rows)
        with (stage / "replicate_matches.tsv").open("w", encoding="utf-8", newline="") as handle:
            handle.write("r1_peak\tr2_peak\toverlap_bp\tr1_signal\tr2_signal\n")
            for first, second, overlap in matches:
                handle.write(f"{first['name']}\t{second['name']}\t{overlap}\t{first['signal']}\t{second['signal']}\n")
        with (stage / "motif_scores.tsv").open("w", encoding="utf-8", newline="") as handle:
            handle.write("set\tscore\n")
            for score in motif_peak_scores: handle.write(f"peak\t{score:.10g}\n")
            for score in motif_control_scores: handle.write(f"control\t{score:.10g}\n")
        versions = {
            "python": sys.version.split()[0], "numpy": np.__version__,
            "scipy": __import__("scipy").__version__, "slurm_job_id": os.environ["SLURM_JOB_ID"],
        }
        (stage / "versions.json").write_text(json.dumps(versions, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        files = [path for path in stage.iterdir() if path.is_file()]
        with (stage / "checksums.sha256").open("w", encoding="ascii", newline="\n") as handle:
            for path in sorted(files): handle.write(f"{sha256(path)}  {path.name}\n")
        (stage / "manifest.json").write_text(json.dumps({
            "schema_version": SCHEMA_VERSION, "type": "real_narrow_evaluation",
            "status": "complete", "slurm_job_id": os.environ["SLURM_JOB_ID"],
            "criteria": criteria,
        }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(stage, args.output_dir)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    print(json.dumps({"status": "complete", "criteria": criteria}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
