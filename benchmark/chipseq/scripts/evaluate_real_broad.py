#!/usr/bin/env python3
"""Evaluate the frozen K562 H3K27me3 Real Broad benchmark without tuning."""

from __future__ import annotations

import argparse
import bisect
import csv
import gzip
import hashlib
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr


EXPECTED_ROOT = Path(
    "/scratch/Schisto-epigenetics/gustavo/helixforge-chipseq-real-broad-benchmark-20260830"
)
CANONICAL_CHROMS = [f"chr{number}" for number in range(1, 23)] + ["chrX", "chrY"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_intervals(path: Path) -> list[dict[str, object]]:
    opener = gzip.open if path.suffix == ".gz" else Path.open
    kwargs = {"mode": "rt", "encoding": "utf-8"} if path.suffix == ".gz" else {
        "mode": "r", "encoding": "utf-8"
    }
    rows = []
    with opener(path, **kwargs) as handle:
        for number, line in enumerate(handle, start=1):
            if not line.strip() or line.startswith(("#", "track", "browser")):
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 3:
                raise ValueError(f"invalid interval row {number}: {path}")
            start, end = int(fields[1]), int(fields[2])
            if start < 0 or end <= start:
                raise ValueError(f"invalid interval coordinates at row {number}: {path}")
            rows.append({"chrom": fields[0], "start": start, "end": end, "fields": fields})
    if not rows:
        raise ValueError(f"empty interval file: {path}")
    return rows


def group_intervals(rows: list[dict[str, object]]) -> dict[str, list[tuple[int, int]]]:
    grouped: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["chrom"])].append((int(row["start"]), int(row["end"])))
    return grouped


def merge_intervals(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[list[int]] = []
    for start, end in sorted(intervals):
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return [(start, end) for start, end in merged]


def union_by_chrom(
    rows: list[dict[str, object]], allowed: set[str] | None = None
) -> dict[str, list[tuple[int, int]]]:
    grouped = group_intervals(
        [row for row in rows if allowed is None or str(row["chrom"]) in allowed]
    )
    return {chrom: merge_intervals(values) for chrom, values in grouped.items()}


def total_length(grouped: dict[str, list[tuple[int, int]]]) -> int:
    return sum(end - start for values in grouped.values() for start, end in values)


def intersection_length(
    left: dict[str, list[tuple[int, int]]], right: dict[str, list[tuple[int, int]]]
) -> int:
    total = 0
    for chrom in left.keys() & right.keys():
        first, second, i, j = left[chrom], right[chrom], 0, 0
        while i < len(first) and j < len(second):
            total += max(0, min(first[i][1], second[j][1]) - max(first[i][0], second[j][0]))
            if first[i][1] <= second[j][1]:
                i += 1
            else:
                j += 1
    return total


def interval_jaccard(
    left: dict[str, list[tuple[int, int]]], right: dict[str, list[tuple[int, int]]]
) -> tuple[int, int, float]:
    overlap = intersection_length(left, right)
    union = total_length(left) + total_length(right) - overlap
    return overlap, union, overlap / union if union else float("nan")


def semantic_coordinates(rows: list[dict[str, object]]) -> list[tuple[str, int, int]]:
    return sorted((str(row["chrom"]), int(row["start"]), int(row["end"])) for row in rows)


def width_summary(rows: list[dict[str, object]]) -> dict[str, float | int]:
    widths = np.asarray([int(row["end"]) - int(row["start"]) for row in rows], dtype=np.int64)
    return {
        "count": int(widths.size), "total_bp": int(widths.sum()),
        "minimum_bp": int(widths.min()), "median_bp": float(np.median(widths)),
        "mean_bp": float(np.mean(widths)), "p90_bp": float(np.quantile(widths, 0.90)),
        "maximum_bp": int(widths.max()),
    }


def parse_fai(path: Path) -> tuple[list[tuple[str, int]], dict[str, int]]:
    ordered, lengths = [], {}
    for line in path.read_text(encoding="ascii").splitlines():
        chrom, length = line.split("\t")[:2]
        ordered.append((chrom, int(length)))
        lengths[chrom] = int(length)
    return ordered, lengths


def run_checked(command: list[str], stdout=subprocess.PIPE) -> subprocess.CompletedProcess:
    return subprocess.run(command, check=True, text=True, stdout=stdout, stderr=subprocess.PIPE)


def binned_mean_coverage(
    bam: Path, ordered_contigs: list[tuple[str, int]], canonical: set[str], bin_bp: int,
    workspace: Path,
) -> tuple[dict[str, np.ndarray], int]:
    bins = workspace / "genome.500bp.bed"
    sizes = workspace / "genome.sizes"
    if not bins.exists():
        with sizes.open("w", encoding="ascii", newline="\n") as size_handle, bins.open(
            "w", encoding="ascii", newline="\n"
        ) as bin_handle:
            for chrom, length in ordered_contigs:
                size_handle.write(f"{chrom}\t{length}\n")
                for start in range(0, length, bin_bp):
                    bin_handle.write(f"{chrom}\t{start}\t{min(length, start + bin_bp)}\n")
    total_reads = int(run_checked(["samtools", "view", "-c", str(bam)]).stdout.strip())
    values = {
        chrom: np.empty((length + bin_bp - 1) // bin_bp, dtype=np.float32)
        for chrom, length in ordered_contigs if chrom in canonical
    }
    positions = defaultdict(int)
    command = [
        "bedtools", "coverage", "-sorted", "-g", str(sizes), "-a", str(bins),
        "-b", str(bam), "-mean",
    ]
    process = subprocess.Popen(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert process.stdout is not None
    scale = 1_000_000.0 / total_reads
    for line in process.stdout:
        fields = line.rstrip("\n").split("\t")
        chrom = fields[0]
        if chrom in values:
            index = positions[chrom]
            values[chrom][index] = float(fields[-1]) * scale
            positions[chrom] += 1
    stderr = process.stderr.read() if process.stderr is not None else ""
    return_code = process.wait()
    if return_code:
        raise RuntimeError(f"bedtools coverage failed for {bam}: {stderr}")
    for chrom, vector in values.items():
        if positions[chrom] != vector.size:
            raise RuntimeError(f"incomplete 500 bp coverage vector for {chrom}: {positions[chrom]}/{vector.size}")
    return values, total_reads


def coverage_correlations(
    first: dict[str, np.ndarray], second: dict[str, np.ndarray], seed: int
) -> dict[str, float | int]:
    chroms = [chrom for chrom in CANONICAL_CHROMS if chrom in first and chrom in second]
    left = np.concatenate([first[chrom] for chrom in chroms])
    right = np.concatenate([second[chrom] for chrom in chroms])
    pearson = float(np.corrcoef(left, right)[0, 1])
    spearman = float(spearmanr(left, right).statistic)
    rng = random.Random(seed)
    rotated_parts, offsets = [], {}
    for chrom in chroms:
        vector = second[chrom]
        offset = rng.randrange(1, vector.size)
        offsets[chrom] = offset
        rotated_parts.append(np.roll(vector, offset))
    rotated = np.concatenate(rotated_parts)
    return {
        "bins": int(left.size), "pearson": pearson, "spearman": spearman,
        "rotated_pearson": float(np.corrcoef(left, rotated)[0, 1]),
        "rotated_spearman": float(spearmanr(left, rotated).statistic),
        "rotation_offsets_bins": offsets,
    }


def rotate_union(
    source: dict[str, list[tuple[int, int]]], lengths: dict[str, int], rng: random.Random
) -> tuple[dict[str, list[tuple[int, int]]], dict[str, int]]:
    rotated, offsets = {}, {}
    for chrom, intervals in source.items():
        length = lengths[chrom]
        offset = rng.randrange(1, length)
        offsets[chrom] = offset
        shifted = []
        for start, end in intervals:
            new_start, new_end = (start + offset) % length, (end + offset) % length
            if new_start < new_end:
                shifted.append((new_start, new_end))
            else:
                if new_start < length:
                    shifted.append((new_start, length))
                if new_end > 0:
                    shifted.append((0, new_end))
        rotated[chrom] = merge_intervals(shifted)
    return rotated, offsets


def external_fragmentation(
    consensus: dict[str, list[tuple[int, int]]], external: dict[str, list[tuple[int, int]]]
) -> dict[str, float | int]:
    external_total = sum(len(values) for values in external.values())
    touched = fragmented = excess = 0
    for chrom, references in external.items():
        calls = consensus.get(chrom, [])
        index = 0
        for start, end in references:
            while index < len(calls) and calls[index][1] <= start:
                index += 1
            neighbours, cursor = 0, index
            while cursor < len(calls) and calls[cursor][0] < end:
                overlap = max(0, min(end, calls[cursor][1]) - max(start, calls[cursor][0]))
                if overlap >= 500 or overlap >= 0.10 * (end - start):
                    neighbours += 1
                cursor += 1
            touched += int(neighbours > 0)
            fragmented += int(neighbours >= 2)
            excess += max(0, neighbours - 1)
    return {
        "external_domains": external_total, "external_domains_touched": touched,
        "external_domains_fragmented": fragmented,
        "fragmentation_rate_all_external": fragmented / external_total,
        "fragmentation_rate_touched_external": fragmented / touched if touched else float("nan"),
        "fragmentation_excess": excess,
        "substantial_edge_rule": "overlap >=500 bp OR >=10% of external domain",
        "interpretation": "descriptive context; ENCODE calls are not ground truth",
    }


def interval_overlaps(values: list[tuple[int, int]], starts: list[int], start: int, end: int) -> bool:
    index = bisect.bisect_left(starts, end) - 1
    return index >= 0 and values[index][1] > start


def annotation_distribution(gtf: Path, rows: list[dict[str, object]]) -> dict[str, int]:
    promoters, exons, genes = defaultdict(list), defaultdict(list), defaultdict(list)
    opener = gzip.open if gtf.suffix == ".gz" else Path.open
    kwargs = {"mode": "rt", "encoding": "utf-8"} if gtf.suffix == ".gz" else {
        "mode": "r", "encoding": "utf-8"
    }
    with opener(gtf, **kwargs) as handle:
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
                promoters[chrom].append(
                    (max(0, start - 2000), start + 500) if fields[6] == "+"
                    else (max(0, end - 500), end + 2000)
                )
    merged = {
        name: {chrom: merge_intervals(values) for chrom, values in source.items()}
        for name, source in (("promoter", promoters), ("exon", exons), ("gene_body", genes))
    }
    starts = {
        name: {chrom: [start for start, _ in values] for chrom, values in source.items()}
        for name, source in merged.items()
    }
    counts = {"promoter": 0, "exon": 0, "intron_or_gene_body": 0, "intergenic": 0}
    for row in rows:
        chrom, start, end = str(row["chrom"]), int(row["start"]), int(row["end"])
        if chrom in merged["promoter"] and interval_overlaps(merged["promoter"][chrom], starts["promoter"][chrom], start, end):
            counts["promoter"] += 1
        elif chrom in merged["exon"] and interval_overlaps(merged["exon"][chrom], starts["exon"][chrom], start, end):
            counts["exon"] += 1
        elif chrom in merged["gene_body"] and interval_overlaps(merged["gene_body"][chrom], starts["gene_body"][chrom], start, end):
            counts["intron_or_gene_body"] += 1
        else:
            counts["intergenic"] += 1
    return counts


def read_peak_qc(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return {row["record_id"]: row for row in csv.DictReader(handle, delimiter="\t")}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark-root", required=True, type=Path)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    if "SLURM_JOB_ID" not in os.environ:
        raise RuntimeError("evaluation must run in a Slurm allocation")
    root = args.benchmark_root.resolve()
    if root != EXPECTED_ROOT or args.output_dir.exists():
        raise ValueError("unexpected benchmark root or existing evaluation output")

    config = json.loads((args.repo_root / "benchmark/chipseq/configs/real_broad_execution.json").read_text(encoding="utf-8"))
    evaluation = config["evaluation"]
    hf = root / "helixforge/results"
    independent = root / "independent"
    hf_r1_path = hf / "080-peak-calling/ENCFF000BXP.H3K27me3.broad.macs3.peak_calling/peaks.broadPeak"
    hf_r2_path = hf / "080-peak-calling/ENCFF000BXN.H3K27me3.broad.macs3.peak_calling/peaks.broadPeak"
    consensus_matches = list((hf / "chipseq/consensus").glob("*/*/consolidated_peaks.bed"))
    if len(consensus_matches) != 1:
        raise RuntimeError(f"expected one HelixForge consensus, found {len(consensus_matches)}")
    hf_consensus_path = consensus_matches[0]
    ind_r1_path = independent / "peaks/ENCFF000BXP/ENCFF000BXP_peaks.broadPeak"
    ind_r2_path = independent / "peaks/ENCFF000BXN/ENCFF000BXN_peaks.broadPeak"
    ind_consensus_path = independent / "consensus/consolidated_peaks.bed"
    external_path = root / "downloads/external/ENCFF049HUP.bed.gz"
    gtf_path = root / "reference/annotation.gtf"
    fai_path = root / "reference/genome.fa.fai"

    hf_r1, hf_r2, hf_consensus = map(read_intervals, (hf_r1_path, hf_r2_path, hf_consensus_path))
    ind_r1, ind_r2, ind_consensus = map(read_intervals, (ind_r1_path, ind_r2_path, ind_consensus_path))
    external = read_intervals(external_path)
    canonical = set(CANONICAL_CHROMS)
    ordered_contigs, lengths = parse_fai(fai_path)
    shared = canonical & set(lengths) & {str(row["chrom"]) for row in external}

    implementation = {}
    for name, left, right in (
        ("replicate_1", hf_r1, ind_r1), ("replicate_2", hf_r2, ind_r2),
        ("consensus", hf_consensus, ind_consensus),
    ):
        left_union, right_union = union_by_chrom(left, shared), union_by_chrom(right, shared)
        overlap, union, jaccard = interval_jaccard(left_union, right_union)
        implementation[name] = {
            "helixforge_count": len(left), "independent_count": len(right),
            "coordinate_equal": semantic_coordinates(left) == semantic_coordinates(right),
            "overlap_bp": overlap, "union_bp": union, "base_jaccard": jaccard,
        }

    peak_qc = read_peak_qc(hf / "chipseq/peak_qc/peak_qc_summary.tsv")
    for sample in ("ENCFF000BXP", "ENCFF000BXN"):
        if sample not in peak_qc or peak_qc[sample]["control_id"] != "ENCFF000BWK":
            raise RuntimeError(f"invalid sample/control association for {sample}")

    workspace = Path(tempfile.mkdtemp(prefix=".real-broad-coverage.", dir=root))
    try:
        r1_coverage, r1_reads = binned_mean_coverage(
            independent / "bam/ENCFF000BXP.final.bam", ordered_contigs, canonical,
            int(evaluation["coverage_bin_bp"]), workspace,
        )
        r2_coverage, r2_reads = binned_mean_coverage(
            independent / "bam/ENCFF000BXN.final.bam", ordered_contigs, canonical,
            int(evaluation["coverage_bin_bp"]), workspace,
        )
        coverage = coverage_correlations(
            r1_coverage, r2_coverage, int(evaluation["replicate_rotation_seed"])
        )
        coverage.update({"replicate_1_reads": r1_reads, "replicate_2_reads": r2_reads,
                         "bin_bp": int(evaluation["coverage_bin_bp"]), "normalization": "CPM"})
    finally:
        shutil.rmtree(workspace, ignore_errors=True)

    consensus_union = union_by_chrom(hf_consensus, shared)
    external_union = union_by_chrom(external, shared)
    observed_overlap, observed_union, observed_jaccard = interval_jaccard(consensus_union, external_union)
    rng = random.Random(int(evaluation["encode_rotation_seed"]))
    null_rows, exceedances = [], 0
    for index in range(1, int(evaluation["encode_rotation_sets"]) + 1):
        rotated, offsets = rotate_union(consensus_union, lengths, rng)
        overlap, union, jaccard = interval_jaccard(rotated, external_union)
        exceedances += int(overlap >= observed_overlap)
        null_rows.append({
            "null_id": index, "overlap_bp": overlap, "union_bp": union, "jaccard": jaccard,
            "offsets_sha256": hashlib.sha256(json.dumps(offsets, sort_keys=True).encode()).hexdigest(),
        })
    empirical_p = (1 + exceedances) / (1 + int(evaluation["encode_rotation_sets"]))

    hf_r1_union, hf_r2_union = union_by_chrom(hf_r1, shared), union_by_chrom(hf_r2, shared)
    replicate_overlap, replicate_union, replicate_jaccard = interval_jaccard(hf_r1_union, hf_r2_union)
    annotations = annotation_distribution(gtf_path, hf_consensus)
    fragmentation = external_fragmentation(consensus_union, external_union)
    all_equal = all(item["coordinate_equal"] for item in implementation.values())
    rb1_pass = bool(
        len(hf_r1) and len(hf_r2) and len(hf_consensus) and all_equal
        and peak_qc["ENCFF000BXP"]["control_id"] == "ENCFF000BWK"
        and peak_qc["ENCFF000BXN"]["control_id"] == "ENCFF000BWK"
    )
    criteria = {
        "RB1": {"type": "RELEASE_GATE", "pass": rb1_pass},
        "RB2": {"type": "SANITY_CHECK", "pass": bool(coverage["pearson"] > 0 and coverage["pearson"] > coverage["rotated_pearson"]),
                "value": coverage["pearson"], "rotated_value": coverage["rotated_pearson"]},
        "RB3": {"type": "EXPECTED_RANGE", "pass": empirical_p <= float(evaluation["empirical_p_threshold"]),
                "value": empirical_p},
        "RB4": {"type": "DESCRIPTIVE", "pass": None},
        "RB5": {"type": "DESCRIPTIVE", "pass": None},
    }
    dataset_limitations = [
        "ENCODE_NOT_COMPLIANT_INSUFFICIENT_USABLE_READ_DEPTH",
        "ENCODE_WARNING_LOW_36BP_READ_LENGTH",
        "ENCODE_WARNING_MIXED_REPLICATE_READ_LENGTHS",
        "EXTERNAL_BIGWIG_CONCORDANCE_NOT_COMPUTED_NO_FROZEN_BIGWIG_READER",
    ]
    classification = "FAIL" if not rb1_pass else (
        "PASS_WITH_LIMITATIONS" if dataset_limitations or not criteria["RB2"]["pass"] or not criteria["RB3"]["pass"] else "PASS"
    )
    metrics = {
        "implementation": implementation,
        "counts_and_widths": {
            "replicate_1": width_summary(hf_r1), "replicate_2": width_summary(hf_r2),
            "consensus": width_summary(hf_consensus), "encode_reference": width_summary(external),
        },
        "frip": {
            sample: {
                "total_reads": int(peak_qc[sample]["total_units"]),
                "reads_in_peaks": int(peak_qc[sample]["units_in_peaks"]),
                "frip": float(peak_qc[sample]["frip"]),
            } for sample in ("ENCFF000BXP", "ENCFF000BXN")
        },
        "replicate_peak_overlap": {"overlap_bp": replicate_overlap, "union_bp": replicate_union, "jaccard": replicate_jaccard},
        "replicate_coverage": coverage,
        "encode_overlap": {
            "accession": "ENCFF049HUP", "observed_overlap_bp": observed_overlap,
            "observed_union_bp": observed_union, "observed_jaccard": observed_jaccard,
            "null_method": "chromosome-preserving rigid circular rotation",
            "null_sets": int(evaluation["encode_rotation_sets"]), "null_exceedances": exceedances,
            "empirical_p": empirical_p,
        },
        "external_fragmentation_context": fragmentation,
        "synthetic_broad_fragmentation_reference": float(evaluation["synthetic_broad_fragmentation_reference"]),
        "annotation_distribution": annotations,
        "external_signal_track": {"accession": "ENCFF366NNJ", "status": "NOT_COMPUTED", "reason": "no BigWig reader in frozen runtime; RB5 is descriptive"},
        "dataset_limitations": dataset_limitations,
    }
    summary = {
        "schema_version": "1.0", "benchmark_id": config["benchmark_id"],
        "classification": classification, "criteria": criteria,
        "technical_execution": "PASS", "independent_concordance": "PASS" if all_equal else "FAIL",
        "scientific_target": config["scientific_target"], "protocol_commit": config["protocol_commit"],
        "slurm_job_id": os.environ["SLURM_JOB_ID"], "limitations": dataset_limitations,
    }

    args.output_dir.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".real-broad-evaluation.", dir=args.output_dir.parent))
    try:
        for name, payload in (("metrics.json", metrics), ("criteria.json", criteria), ("benchmark_summary.json", summary)):
            (stage / name).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        with (stage / "null_overlap.tsv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(null_rows[0]), delimiter="\t", lineterminator="\n")
            writer.writeheader(); writer.writerows(null_rows)
        with (stage / "annotation_distribution.tsv").open("w", encoding="utf-8", newline="") as handle:
            handle.write("category\tconsensus_domains\n")
            for category, count in annotations.items():
                handle.write(f"{category}\t{count}\n")
        with (stage / "implementation_comparison.tsv").open("w", encoding="utf-8", newline="") as handle:
            handle.write("artifact\thelixforge_count\tindependent_count\tcoordinate_equal\tbase_jaccard\n")
            for artifact, row in implementation.items():
                handle.write(f"{artifact}\t{row['helixforge_count']}\t{row['independent_count']}\t{str(row['coordinate_equal']).lower()}\t{row['base_jaccard']:.12g}\n")
        versions = {
            "python": sys.version.split()[0], "numpy": np.__version__,
            "scipy": __import__("scipy").__version__,
            "bedtools": run_checked(["bedtools", "--version"]).stdout.strip(),
            "samtools": run_checked(["samtools", "--version"]).stdout.splitlines()[0],
        }
        (stage / "versions.json").write_text(json.dumps(versions, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        files = sorted(path for path in stage.iterdir() if path.is_file())
        with (stage / "checksums.sha256").open("w", encoding="ascii", newline="\n") as handle:
            for path in files:
                handle.write(f"{sha256(path)}  {path.name}\n")
        (stage / "manifest.json").write_text(json.dumps({
            "schema_version": "1.0", "type": "real_broad_evaluation", "status": "complete",
            "classification": classification, "slurm_job_id": os.environ["SLURM_JOB_ID"],
            "criteria": criteria,
        }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(stage, args.output_dir)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
