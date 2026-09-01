#!/usr/bin/env python3
"""Audit exact-GC null-stratum capacity without generating nulls or RN3."""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import shutil
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from evaluate_real_narrow import (
    FastaReader,
    gc_decile,
    interval_overlaps,
    merge_intervals,
    read_peaks,
    sha256,
)


MASTER_SEED = 20261002
MIN_PARENT_POOL = 200
PARENT_POOL_MULTIPLIER = 20
MAX_POOL_ATTEMPT_MULTIPLIER = 10000


def percentile(values: list[float], value: float) -> float:
    return float(np.quantile(np.asarray(values, dtype=np.float64), value, method="linear"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    if "SLURM_JOB_ID" not in os.environ:
        raise RuntimeError("exact-GC capacity preflight must run in a Slurm allocation")
    root = args.benchmark_root.resolve()
    expected = Path("/scratch/Schisto-epigenetics/gustavo/helixforge-chipseq-real-narrow-benchmark-20260830")
    if root != expected or args.output_dir.exists():
        raise ValueError("unexpected benchmark root or existing exact-GC preflight output")

    hf_idr_path = next((root / "helixforge/results/chipseq/consensus").glob("*/*/idr_output.narrowPeak"))
    external_path = root / "downloads/external/ENCFF519CXF.bed.gz"
    fasta = FastaReader(root / "reference/genome.fa", root / "reference/genome.fa.fai")
    observed = read_peaks(hf_idr_path)
    external = read_peaks(external_path, require_summit=False)
    shared = set(fasta.index) & {str(peak["chrom"]) for peak in external}
    observed = [peak for peak in observed if peak["chrom"] in shared]

    blacklist_intervals: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for line in (root / "reference/blacklist.bed").read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            chrom, start, end = line.split("\t")[:3]
            blacklist_intervals[chrom].append((int(start), int(end)))
    blacklist = {chrom: merge_intervals(values) for chrom, values in blacklist_intervals.items()}

    peaks_by_chrom: dict[str, list[dict[str, object]]] = defaultdict(list)
    for peak in observed:
        peaks_by_chrom[str(peak["chrom"])].append(peak)
    rng = random.Random(MASTER_SEED)
    exact_rows = []
    parent_rows = []

    for chrom in sorted(shared):
        chrom_peaks = peaks_by_chrom.get(chrom, [])
        if not chrom_peaks:
            continue
        sequence = fasta.read_chrom(chrom)
        encoded = np.frombuffer(sequence, dtype=np.uint8)
        valid = np.isin(encoded, np.frombuffer(b"ACGT", dtype=np.uint8))
        gc = (encoded == ord("G")) | (encoded == ord("C"))
        valid_prefix = np.concatenate((np.zeros(1, dtype=np.uint64), np.cumsum(valid, dtype=np.uint64)))
        gc_prefix = np.concatenate((np.zeros(1, dtype=np.uint64), np.cumsum(gc, dtype=np.uint64)))
        starts = np.asarray([peak["start"] for peak in chrom_peaks], dtype=np.int64)
        ends = np.asarray([peak["end"] for peak in chrom_peaks], dtype=np.int64)
        widths = ends - starts
        observed_gc = gc_prefix[ends] - gc_prefix[starts]
        observed_valid = valid_prefix[ends] - valid_prefix[starts]
        if np.any(observed_valid != widths):
            raise ValueError(f"observed peak contains non-ACGT bases on {chrom}")

        exact_counts: Counter[tuple[int, int]] = Counter()
        parent_counts: Counter[tuple[int, int]] = Counter()
        for width, gc_bases, valid_bases in zip(widths, observed_gc, observed_valid):
            width, gc_bases = int(width), int(gc_bases)
            exact_counts[(width, gc_bases)] += 1
            parent_counts[(width, gc_decile(gc_bases, int(valid_bases)))] += 1

        chrom_blacklist = blacklist.get(chrom, [])
        blacklist_starts = [start for start, _end in chrom_blacklist]
        for (width, descriptive_decile), parent_k in sorted(parent_counts.items()):
            target = max(MIN_PARENT_POOL, PARENT_POOL_MULTIPLIER * parent_k)
            max_attempts = max(10000, MAX_POOL_ATTEMPT_MULTIPLIER * target)
            candidates: dict[int, int] = {}
            attempts = 0
            while len(candidates) < target and attempts < max_attempts:
                attempts += 1
                start = rng.randrange(0, fasta.index[chrom][0] - width + 1)
                if start in candidates:
                    continue
                end = start + width
                if interval_overlaps(chrom_blacklist, blacklist_starts, start, end):
                    continue
                valid_bases = int(valid_prefix[end] - valid_prefix[start])
                if valid_bases != width:
                    continue
                gc_bases = int(gc_prefix[end] - gc_prefix[start])
                if gc_decile(gc_bases, valid_bases) != descriptive_decile:
                    continue
                candidates[start] = gc_bases
            if len(candidates) < target:
                raise RuntimeError(
                    f"parent capacity failed for {chrom}, width={width}, decile={descriptive_decile}: "
                    f"{len(candidates)}/{target} after {attempts} probes"
                )
            candidate_gc_counts = Counter(candidates.values())
            parent_rows.append({
                "chrom": chrom, "width": width, "descriptive_gc_decile": descriptive_decile,
                "observed_peaks": parent_k, "parent_pool_M": len(candidates),
                "parent_capacity_ratio": len(candidates) / parent_k, "random_probes": attempts,
            })
            for (exact_width, exact_gc), k in sorted(exact_counts.items()):
                if exact_width != width or gc_decile(exact_gc, exact_width) != descriptive_decile:
                    continue
                M = candidate_gc_counts.get(exact_gc, 0)
                exact_rows.append({
                    "stratum_id": f"{chrom}:{width}:{exact_gc}",
                    "chrom": chrom,
                    "width": width,
                    "exact_gc_bases": exact_gc,
                    "descriptive_gc_decile": descriptive_decile,
                    "k": k,
                    "M": M,
                    "capacity_ratio": M / k,
                    "sampling_feasible": M >= k,
                })

    ratios = [float(row["capacity_ratio"]) for row in exact_rows]
    infeasible = [row for row in exact_rows if not row["sampling_feasible"]]
    peak_buckets = {
        "lt_2": sum(int(row["k"]) for row in exact_rows if row["capacity_ratio"] < 2),
        "ge_2_lt_5": sum(int(row["k"]) for row in exact_rows if 2 <= row["capacity_ratio"] < 5),
        "ge_5_lt_10": sum(int(row["k"]) for row in exact_rows if 5 <= row["capacity_ratio"] < 10),
        "ge_10_lt_20": sum(int(row["k"]) for row in exact_rows if 10 <= row["capacity_ratio"] < 20),
        "ge_20": sum(int(row["k"]) for row in exact_rows if row["capacity_ratio"] >= 20),
    }
    status = "PASS" if not infeasible else "FAIL_NOT_EVALUABLE"
    summary = {
        "schema_version": "1.0",
        "phase": "EXACT_GC_CAPACITY_PREFLIGHT",
        "status": status,
        "master_seed": MASTER_SEED,
        "operational_stratum": "chromosome x exact width x exact GC-base count",
        "descriptive_gc_superclass": "decile",
        "candidate_universe": "deterministic uniformly sampled eligible parent pool, partitioned by exact GC-base count",
        "rn3_calculated": False,
        "null_sets_generated": False,
        "number_of_strata": len(exact_rows),
        "strata_with_k_1": sum(row["k"] == 1 for row in exact_rows),
        "strata_with_M_lt_k": len(infeasible),
        "observed_peaks_in_infeasible_strata": sum(int(row["k"]) for row in infeasible),
        "capacity_ratio": {
            "minimum": min(ratios),
            "p01": percentile(ratios, 0.01),
            "p05": percentile(ratios, 0.05),
            "median": percentile(ratios, 0.50),
            "p95": percentile(ratios, 0.95),
        },
        "observed_peak_capacity_buckets": peak_buckets,
        "failure_policy": "RN3 = NOT_EVALUABLE_UNDER_FROZEN_CONTROL_REQUIREMENTS if any M_g < k_g",
        "slurm_job_id": os.environ["SLURM_JOB_ID"],
    }

    args.output_dir.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".real-narrow-exact-gc-capacity.", dir=args.output_dir.parent))
    try:
        for filename, rows in (("exact_gc_capacity.tsv", exact_rows), ("parent_pool_capacity.tsv", parent_rows)):
            with (stage / filename).open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n")
                writer.writeheader(); writer.writerows(rows)
        summary_text = json.dumps(summary, indent=2, sort_keys=True) + "\n"
        (stage / "summary.json").write_text(summary_text, encoding="utf-8")
        (stage / "manifest.json").write_text(summary_text, encoding="utf-8")
        with (stage / "checksums.sha256").open("w", encoding="ascii", newline="\n") as handle:
            for path in sorted(
                item for item in stage.iterdir()
                if item.is_file() and item.name != "checksums.sha256"
            ):
                handle.write(f"{sha256(path)}  {path.name}\n")
        os.replace(stage, args.output_dir)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    print(json.dumps({"status": status, "rn3_calculated": False, "null_sets_generated": False}))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
