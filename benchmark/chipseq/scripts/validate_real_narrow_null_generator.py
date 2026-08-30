#!/usr/bin/env python3
"""Generate and audit Real Narrow null sets without calculating RN3."""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import math
import os
import random
import shutil
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import binom

from evaluate_real_narrow import (
    FastaReader,
    gc_decile,
    group_intervals,
    interval_overlaps,
    merge_intervals,
    read_peaks,
    sha256,
    total_length,
)


SCHEMA_VERSION = "1.0"
MASTER_SEED = 20261002
NULL_SETS = 100
MAX_CANDIDATE_SETS = 2000
GC_TOLERANCE = 0.005
MIN_POOL_SIZE = 200
POOL_MULTIPLIER = 20
MAX_POOL_ATTEMPT_MULTIPLIER = 10000
MIN_EXPECTED_UNIQUE = 50.0
MIN_UNIQUE_EXPECTATION_RATIO = 0.80
GLOBAL_MAX_REUSE_ALPHA = 0.01
V2_SAMPLER_RETIRED = True


def deterministic_gzip_text(path: Path):
    raw = path.open("wb")
    compressed = gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0)
    return raw, compressed, io.TextIOWrapper(compressed, encoding="utf-8", newline="")


def balanced_uniform_draw(
    groups: list[dict[str, object]],
    target_gc: int,
    total_bases: int,
    rng: random.Random,
) -> tuple[list[list[tuple[int, int]]], int, int] | None:
    """Draw uniformly per stratum, then repair only the aggregate GC total."""
    selections = [rng.sample(group["pool"], int(group["k"])) for group in groups]
    current_gc = sum(int(gc_bases) for selected in selections for _start, gc_bases in selected)
    tolerance_bases = math.floor(GC_TOLERANCE * total_bases)
    if abs(current_gc - target_gc) <= tolerance_bases:
        return selections, current_gc, 0

    direction = 1 if current_gc < target_gc else -1
    moves = []
    for group_index, (group, selected) in enumerate(zip(groups, selections)):
        selected_starts = {int(start) for start, _gc in selected}
        selected_order = list(enumerate(selected))
        rng.shuffle(selected_order)
        selected_order.sort(key=lambda row: int(row[1][1]), reverse=direction < 0)

        alternatives = [candidate for candidate in group["pool"] if int(candidate[0]) not in selected_starts]
        rng.shuffle(alternatives)
        alternatives.sort(key=lambda row: int(row[1]), reverse=direction > 0)
        for (selected_index, old), new in zip(selected_order, alternatives):
            improvement = direction * (int(new[1]) - int(old[1]))
            if improvement > 0:
                moves.append((improvement, group_index, selected_index, new))

    rng.shuffle(moves)
    gap = direction * (target_gc - current_gc)
    swaps = 0
    for improvement, group_index, selected_index, replacement in moves:
        if gap <= tolerance_bases:
            break
        if improvement > gap + tolerance_bases:
            continue
        old = selections[group_index][selected_index]
        selections[group_index][selected_index] = replacement
        current_gc += int(replacement[1]) - int(old[1])
        gap = direction * (target_gc - current_gc)
        swaps += 1

    if abs(current_gc - target_gc) > tolerance_bases:
        return None
    return selections, current_gc, swaps


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--run-label", required=True, choices=("run_a", "run_b"))
    args = parser.parse_args()
    if "SLURM_JOB_ID" not in os.environ:
        raise RuntimeError("null validation must run in a Slurm allocation")
    if V2_SAMPLER_RETIRED:
        raise RuntimeError(
            "the GC-decile plus balanced-swap V2 sampler is retired; "
            "use the exact-GC capacity preflight"
        )
    root = args.benchmark_root.resolve()
    expected = Path("/scratch/Schisto-epigenetics/gustavo/helixforge-chipseq-real-narrow-benchmark-20260830")
    if root != expected or args.output_dir.exists():
        raise ValueError("unexpected benchmark root or existing null-validation output")

    hf_idr_path = next((root / "helixforge/results/chipseq/consensus").glob("*/*/idr_output.narrowPeak"))
    external_path = root / "downloads/external/ENCFF519CXF.bed.gz"
    fasta_path = root / "reference/genome.fa"
    fai_path = root / "reference/genome.fa.fai"
    blacklist_path = root / "reference/blacklist.bed"

    hf_idr = read_peaks(hf_idr_path)
    external = read_peaks(external_path, require_summit=False)
    fasta = FastaReader(fasta_path, fai_path)
    shared = set(fasta.index) & {str(peak["chrom"]) for peak in external}
    comparison_idr = [peak for peak in hf_idr if peak["chrom"] in shared]

    blacklist_intervals: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for line in blacklist_path.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            chrom, start, end = line.split("\t")[:3]
            blacklist_intervals[chrom].append((int(start), int(end)))
    blacklist_merged = {chrom: merge_intervals(values) for chrom, values in blacklist_intervals.items()}

    rng = random.Random(MASTER_SEED)
    peaks_by_chrom: dict[str, list[dict[str, object]]] = defaultdict(list)
    for peak in comparison_idr:
        peaks_by_chrom[str(peak["chrom"])].append(peak)

    groups: list[dict[str, object]] = []
    capacity_rows = []
    observed_gc = observed_bases = 0
    for chrom in sorted(shared):
        sequence = fasta.read_chrom(chrom)
        encoded = np.frombuffer(sequence, dtype=np.uint8)
        valid = np.isin(encoded, np.frombuffer(b"ACGT", dtype=np.uint8))
        gc = (encoded == ord("G")) | (encoded == ord("C"))
        valid_prefix = np.concatenate((np.zeros(1, dtype=np.uint64), np.cumsum(valid, dtype=np.uint64)))
        gc_prefix = np.concatenate((np.zeros(1, dtype=np.uint64), np.cumsum(gc, dtype=np.uint64)))
        chrom_peaks = peaks_by_chrom.get(chrom, [])
        if not chrom_peaks:
            continue
        starts = np.asarray([peak["start"] for peak in chrom_peaks], dtype=np.int64)
        ends = np.asarray([peak["end"] for peak in chrom_peaks], dtype=np.int64)
        widths = ends - starts
        peak_gc = gc_prefix[ends] - gc_prefix[starts]
        peak_valid = valid_prefix[ends] - valid_prefix[starts]
        if np.any(peak_valid != widths):
            raise ValueError(f"observed peak contains non-ACGT bases on {chrom}")
        observed_gc += int(np.sum(peak_gc))
        observed_bases += int(np.sum(peak_valid))

        strata: dict[tuple[int, int], int] = Counter()
        for width, gc_bases, valid_bases in zip(widths, peak_gc, peak_valid):
            strata[(int(width), gc_decile(int(gc_bases), int(valid_bases)))] += 1
        blacklist = blacklist_merged.get(chrom, [])
        blacklist_starts = [start for start, _end in blacklist]
        for (width, gc_class), k in sorted(strata.items()):
            target = max(MIN_POOL_SIZE, POOL_MULTIPLIER * k)
            max_attempts = max(10000, MAX_POOL_ATTEMPT_MULTIPLIER * target)
            candidates: dict[int, int] = {}
            attempts = 0
            while len(candidates) < target and attempts < max_attempts:
                attempts += 1
                start = rng.randrange(0, fasta.index[chrom][0] - width + 1)
                if start in candidates:
                    continue
                end = start + width
                if interval_overlaps(blacklist, blacklist_starts, start, end):
                    continue
                valid_bases = int(valid_prefix[end] - valid_prefix[start])
                if valid_bases != width:
                    continue
                gc_bases = int(gc_prefix[end] - gc_prefix[start])
                if gc_decile(gc_bases, valid_bases) != gc_class:
                    continue
                candidates[start] = gc_bases
            if len(candidates) < target:
                raise RuntimeError(
                    f"capacity failed for {chrom}, width={width}, GC={gc_class}: "
                    f"{len(candidates)}/{target} after {attempts} probes"
                )
            stratum_id = f"{chrom}:{width}:{gc_class}"
            pool = sorted(candidates.items())
            groups.append({
                "stratum_id": stratum_id, "chrom": chrom, "width": width,
                "gc_class": gc_class, "k": k, "pool": pool, "reuse": Counter(),
            })
            capacity_rows.append({
                "stratum_id": stratum_id, "chrom": chrom, "width": width,
                "gc_class": gc_class, "k": k, "M": len(pool),
                "capacity_ratio": len(pool) / k, "random_probes": attempts,
            })

    total_pool = sum(len(group["pool"]) for group in groups)
    args.output_dir.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".real-narrow-null-{args.run_label}.", dir=args.output_dir.parent))
    null_audit_rows = []
    candidate_sets_examined = 0
    raw_handle = compressed_handle = text_handle = None
    try:
        raw_handle, compressed_handle, text_handle = deterministic_gzip_text(stage / "null_sets.tsv.gz")
        writer = csv.writer(text_handle, delimiter="\t", lineterminator="\n")
        writer.writerow(("null_id", "stratum_id", "chrom", "start", "end", "width", "gc_class", "gc_bases"))
        accepted = 0
        while accepted < NULL_SETS and candidate_sets_examined < MAX_CANDIDATE_SETS:
            candidate_sets_examined += 1
            draw = balanced_uniform_draw(groups, observed_gc, observed_bases, rng)
            if draw is None:
                continue
            selections, selected_gc, swaps = draw
            gc_difference = abs(selected_gc / observed_bases - observed_gc / observed_bases)
            if gc_difference > GC_TOLERANCE:
                continue
            accepted += 1
            intervals_by_chrom: dict[str, list[tuple[int, int]]] = defaultdict(list)
            exact_intervals = set()
            for group, selected in zip(groups, selections):
                chrom, width = str(group["chrom"]), int(group["width"])
                reuse: Counter[int] = group["reuse"]
                for start, gc_bases in selected:
                    end = int(start) + width
                    reuse[int(start)] += 1
                    intervals_by_chrom[chrom].append((int(start), end))
                    exact_intervals.add((chrom, int(start), end))
                    writer.writerow((
                        accepted, group["stratum_id"], chrom, int(start), end,
                        width, group["gc_class"], int(gc_bases),
                    ))
            total_width = sum(end - start for values in intervals_by_chrom.values() for start, end in values)
            union_width = sum(
                total_length({chrom: merge_intervals(values)})
                for chrom, values in intervals_by_chrom.items()
            )
            null_audit_rows.append({
                "null_id": accepted,
                "candidate_index": candidate_sets_examined,
                "gc_fraction": selected_gc / observed_bases,
                "gc_absolute_difference": gc_difference,
                "balanced_swaps": swaps,
                "exact_duplicate_intervals": len(comparison_idr) - len(exact_intervals),
                "within_null_overlap_bp": total_width - union_width,
                "within_null_overlap_fraction": (total_width - union_width) / total_width,
            })
        text_handle.flush(); text_handle.close()
        compressed_handle = text_handle = None
        raw_handle.close(); raw_handle = None
        if accepted != NULL_SETS:
            raise RuntimeError(f"generated only {accepted}/{NULL_SETS} GC-matched null sets")

        strata_audit = []
        diversity_pass = True
        for group, capacity in zip(groups, capacity_rows):
            M, k = int(capacity["M"]), int(capacity["k"])
            expected_unique = M * (1.0 - (1.0 - k / M) ** NULL_SETS)
            observed_unique = len(group["reuse"])
            ratio = observed_unique / expected_unique
            quantile = int(binom.ppf(1.0 - GLOBAL_MAX_REUSE_ALPHA / total_pool, NULL_SETS, k / M))
            maximum_reuse = max(group["reuse"].values(), default=0)
            unique_gate = expected_unique < MIN_EXPECTED_UNIQUE or ratio >= MIN_UNIQUE_EXPECTATION_RATIO
            reuse_gate = maximum_reuse <= quantile
            diversity_pass &= unique_gate and reuse_gate
            strata_audit.append({
                **capacity,
                "expected_unique": expected_unique,
                "observed_unique": observed_unique,
                "observed_expected_unique_ratio": ratio,
                "max_reuse": maximum_reuse,
                "max_reuse_binomial_quantile": quantile,
                "unique_gate_pass": unique_gate,
                "reuse_gate_pass": reuse_gate,
            })

        gates = {
            "capacity": min(row["capacity_ratio"] for row in capacity_rows) >= POOL_MULTIPLIER,
            "chromosome_width_gc_class_preserved": True,
            "aggregate_gc": all(row["gc_absolute_difference"] <= GC_TOLERANCE for row in null_audit_rows),
            "within_null_exact_duplicates": all(row["exact_duplicate_intervals"] == 0 for row in null_audit_rows),
            "stratum_diversity": bool(diversity_pass),
            "rn3_not_calculated": True,
        }
        status = "validated" if all(gates.values()) else "failed"

        for filename, rows in (
            ("strata_audit.tsv", strata_audit),
            ("null_set_audit.tsv", null_audit_rows),
        ):
            with (stage / filename).open("w", encoding="utf-8", newline="") as handle:
                tab_writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n")
                tab_writer.writeheader(); tab_writer.writerows(rows)
        summary = {
            "schema_version": SCHEMA_VERSION,
            "status": status,
            "phase": "NULL_GENERATOR_VALIDATION",
            "run_label": args.run_label,
            "master_seed": MASTER_SEED,
            "same_seed_not_same_sequence_across_algorithms": True,
            "null_sets": NULL_SETS,
            "candidate_sets_examined": candidate_sets_examined,
            "observed_peaks": len(comparison_idr),
            "candidate_pool_positions": total_pool,
            "minimum_capacity_ratio": min(row["capacity_ratio"] for row in capacity_rows),
            "gates": gates,
            "diversity_contract": {
                "minimum_expected_unique": MIN_EXPECTED_UNIQUE,
                "minimum_observed_expected_unique_ratio": MIN_UNIQUE_EXPECTATION_RATIO,
                "max_reuse_quantile": "Binomial(100,k_g/M_g), family-wise alpha 0.01",
            },
            "rn3": {"calculated": False},
            "slurm_job_id": os.environ["SLURM_JOB_ID"],
        }
        (stage / "audit_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        checked = sorted(path for path in stage.iterdir() if path.is_file())
        with (stage / "checksums.sha256").open("w", encoding="ascii", newline="\n") as handle:
            for path in checked:
                handle.write(f"{sha256(path)}  {path.name}\n")
        (stage / "manifest.json").write_text(json.dumps({
            **summary,
            "null_sets_sha256": sha256(stage / "null_sets.tsv.gz"),
        }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(stage, args.output_dir)
    except Exception:
        if text_handle is not None:
            text_handle.close()
        elif compressed_handle is not None:
            compressed_handle.close()
        if raw_handle is not None:
            raw_handle.close()
        shutil.rmtree(stage, ignore_errors=True)
        raise

    print(json.dumps({"status": status, "gates": gates, "rn3_calculated": False}))
    return 0 if status == "validated" else 1


if __name__ == "__main__":
    raise SystemExit(main())
