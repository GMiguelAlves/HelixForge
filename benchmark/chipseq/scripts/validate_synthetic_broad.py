#!/usr/bin/env python3
"""Validate the amended frozen synthetic broad truth and FASTQ dataset."""

from __future__ import annotations

import argparse
import importlib.util
import json
from collections import Counter, defaultdict
from pathlib import Path


REQUIRED_TRUTH = (
    "broad_true_domains.bed",
    "broad_domain_strength.tsv",
    "broad_negative_regions.bed",
    "broad_boundary_mappability_probes.fa",
    "broad_simulation_manifest.json",
)
REQUIRED_REFERENCE = (
    "synthetic_chip_v1.fa",
    "synthetic_chip_v1.fa.fai",
    "synthetic_chip_v1.repeats.bed",
    "synthetic_chip_v1.annotation.gtf",
    "reference_manifest.json",
)


def load_sibling(name: str, filename: str):
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if not spec or not spec.loader:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


COMMON = load_sibling("synthetic_validation_common", "validate_synthetic_narrow.py")
PLACEMENT = load_sibling("synthetic_broad_placement", "prepare_synthetic_broad.py")
sha256 = COMMON.sha256
write_json = COMMON.write_json
parse_fasta = COMMON.parse_fasta
read_bed = COMMON.read_bed
intervals_overlap = COMMON.intervals_overlap
fastq_stats = COMMON.fastq_stats


def parse_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as handle:
        header = next(handle).rstrip("\n").split("\t")
        return [dict(zip(header, line.rstrip("\n").split("\t"))) for line in handle if line.strip()]


def validate_sam(path: Path, expected_ids: set[str]) -> dict:
    return COMMON.validate_sam(path, expected_ids)


def validate_truth(config: dict, primary: Path, repeat: Path, sam: Path | None, output: Path) -> None:
    for relative in REQUIRED_TRUTH:
        if not (primary / "truth" / relative).is_file():
            raise FileNotFoundError(relative)
    for relative in REQUIRED_REFERENCE:
        if not (primary / "reference" / relative).is_file():
            raise FileNotFoundError(relative)

    deterministic = {}
    for group, names in (("truth", REQUIRED_TRUTH), ("reference", REQUIRED_REFERENCE)):
        for name in names:
            first = primary / group / name
            second = repeat / group / name
            first_hash, second_hash = sha256(first), sha256(second)
            deterministic[f"{group}/{name}"] = first_hash
            if first_hash != second_hash:
                raise ValueError(f"non-deterministic artifact: {group}/{name}")

    sequences = parse_fasta(primary / "reference" / "synthetic_chip_v1.fa")
    reference = config["reference"]
    expected_chromosomes = {f"chrSynthetic{index}" for index in range(1, int(reference["chromosomes"]) + 1)}
    if set(sequences) != expected_chromosomes:
        raise ValueError("reference chromosome set mismatch")
    if any(len(sequence) != int(reference["chromosome_length_bp"]) for sequence in sequences.values()):
        raise ValueError("reference chromosome length mismatch")
    total_bases = sum(len(sequence) for sequence in sequences.values())
    total_gc = sum(sequence.count("G") + sequence.count("C") for sequence in sequences.values())
    observed_gc = total_gc / total_bases
    if abs(observed_gc - float(reference["target_gc_fraction"])) > 1e-12:
        raise ValueError("reference GC mismatch")

    repeat_rows = read_bed(primary / "reference" / "synthetic_chip_v1.repeats.bed", 4)
    raw_repeats: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for row in repeat_rows:
        raw_repeats[row[0]].append((int(row[1]), int(row[2])))
    repeat_bases = sum(end - start for rows in raw_repeats.values() for start, end in rows)
    if abs(repeat_bases / total_bases - float(reference["repeat_fraction"])) > 1e-12:
        raise ValueError("repeat fraction mismatch")

    truth = config["truth"]
    policy = truth["repeat_traversal"]
    if not policy.get("interior_allowed") or not policy.get("require_both_boundaries_eligible"):
        raise ValueError("approved broad repeat-traversal amendment is absent")
    expanded, starts = PLACEMENT.repeat_index(
        [(row[0], int(row[1]), int(row[2]), row[3]) for row in repeat_rows],
        int(policy["boundary_buffer_bp"]),
    )

    domains = read_bed(primary / "truth" / "broad_true_domains.bed", 6)
    negatives = read_bed(primary / "truth" / "broad_negative_regions.bed", 12)
    strength_rows = parse_tsv(primary / "truth" / "broad_domain_strength.tsv")
    if len(domains) != int(truth["domain_count"]) or len(strength_rows) != len(domains):
        raise ValueError("truth domain count mismatch")
    if len(negatives) != int(truth["negative_regions"]):
        raise ValueError("negative count mismatch")
    domain_ids = [row[3] for row in domains]
    if len(set(domain_ids)) != len(domain_ids):
        raise ValueError("duplicate domain IDs")
    strength_by_id = {row["domain_id"]: row for row in strength_rows}
    if set(strength_by_id) != set(domain_ids):
        raise ValueError("strength table IDs do not match domains")

    matrix = Counter()
    by_chrom: dict[str, list[tuple[int, int, str]]] = defaultdict(list)
    repeat_values = []
    for row in domains:
        chrom, start, end, domain_id = row[0], int(row[1]), int(row[2]), row[3]
        details = strength_by_id[domain_id]
        if chrom not in sequences or not (0 <= start < end <= len(sequences[chrom])):
            raise ValueError(f"invalid coordinates for {domain_id}")
        if details["chrom"] != chrom or int(details["start"]) != start or int(details["end"]) != end:
            raise ValueError(f"strength coordinates mismatch for {domain_id}")
        width = end - start
        if width != int(details["width"]):
            raise ValueError(f"width mismatch for {domain_id}")
        width_key = details["width_class"].lower()
        if width_key not in truth["width_classes_bp"]:
            raise ValueError(f"unknown width class for {domain_id}")
        lower, upper = map(int, truth["width_classes_bp"][width_key])
        if not lower <= width <= upper:
            raise ValueError(f"width outside frozen class for {domain_id}")
        signal_key = details["signal_class"].lower()
        if signal_key not in truth["signal_classes"]:
            raise ValueError(f"unknown signal class for {domain_id}")
        if abs(float(details["signal_strength"]) - float(truth["signal_classes"][signal_key])) > 1e-12:
            raise ValueError(f"signal strength mismatch for {domain_id}")
        if not PLACEMENT.boundary_eligible(start, expanded[chrom], starts[chrom], len(sequences[chrom]), 2000):
            raise ValueError(f"ineligible left boundary for {domain_id}")
        if not PLACEMENT.boundary_eligible(end, expanded[chrom], starts[chrom], len(sequences[chrom]), 2000):
            raise ValueError(f"ineligible right boundary for {domain_id}")
        overlap = PLACEMENT.repeat_overlap(start, end, raw_repeats[chrom])
        if overlap != int(details["repeat_overlap_bp"]):
            raise ValueError(f"repeat overlap mismatch for {domain_id}")
        if abs(overlap / width - float(details["repeat_overlap_fraction"])) > 1e-8:
            raise ValueError(f"repeat overlap fraction mismatch for {domain_id}")
        matrix[(width_key, signal_key)] += 1
        by_chrom[chrom].append((start, end, domain_id))
        repeat_values.append(overlap / width)

    expected_cell = int(truth["domains_per_width_strength_cell"])
    expected_matrix = Counter(
        {(width, signal): expected_cell for width in truth["width_classes_bp"] for signal in truth["signal_classes"]}
    )
    if matrix != expected_matrix:
        raise ValueError(f"width-signal matrix mismatch: {matrix}")
    minimum_gap = int(truth["minimum_inter_domain_gap_bp"])
    for chrom, rows in by_chrom.items():
        rows.sort()
        for left, right in zip(rows, rows[1:]):
            if right[0] - left[1] < minimum_gap:
                raise ValueError(f"inter-domain gap violation on {chrom}: {left[2]} {right[2]}")

    domain_by_id = {row[3]: row for row in domains}
    occupied_negatives: dict[str, list[tuple[int, int]]] = defaultdict(list)
    negative_ids = []
    for row in negatives:
        chrom, start, end, negative_id = row[0], int(row[1]), int(row[2]), row[3]
        matched = row[6]
        if matched not in domain_by_id:
            raise ValueError(f"unknown matched domain for {negative_id}")
        truth_row = domain_by_id[matched]
        if chrom != truth_row[0] or end - start != int(truth_row[2]) - int(truth_row[1]):
            raise ValueError(f"negative matching mismatch for {negative_id}")
        if not (0 <= start < end <= len(sequences[chrom])):
            raise ValueError(f"invalid negative coordinates for {negative_id}")
        if not PLACEMENT.boundary_eligible(start, expanded[chrom], starts[chrom], len(sequences[chrom]), 2000):
            raise ValueError(f"ineligible negative boundary for {negative_id}")
        if not PLACEMENT.boundary_eligible(end, expanded[chrom], starts[chrom], len(sequences[chrom]), 2000):
            raise ValueError(f"ineligible negative boundary for {negative_id}")
        if any(intervals_overlap((start, end), (int(item[1]), int(item[2]))) for item in domains if item[0] == chrom):
            raise ValueError(f"negative overlaps truth: {negative_id}")
        if any(intervals_overlap((start, end), interval) for interval in occupied_negatives[chrom]):
            raise ValueError(f"negative overlap: {negative_id}")
        overlap = PLACEMENT.repeat_overlap(start, end, raw_repeats[chrom])
        if overlap != int(row[10]) or abs(overlap / (end - start) - float(row[11])) > 1e-8:
            raise ValueError(f"negative repeat overlap mismatch for {negative_id}")
        occupied_negatives[chrom].append((start, end))
        negative_ids.append(negative_id)

    expected_probes = {f"{identifier}__{side}" for identifier in [*domain_ids, *negative_ids] for side in ("LEFT", "RIGHT")}
    mappability = {"status": "NOT_RUN"}
    if sam is not None:
        mappability = validate_sam(sam, expected_probes)

    result = {
        "schema_version": "1.0",
        "type": "synthetic_broad_truth_validation",
        "status": "BROAD_TRUTH_FROZEN" if mappability["status"] == "PASS" else "STRUCTURE_VALIDATED",
        "reference": {
            "id": reference["id"],
            "chromosomes": len(sequences),
            "total_bases": total_bases,
            "gc_fraction": observed_gc,
            "repeat_fraction": repeat_bases / total_bases,
            "fasta_sha256": sha256(primary / "reference" / "synthetic_chip_v1.fa"),
        },
        "truth": {
            "domain_count": len(domains),
            "negative_count": len(negatives),
            "width_signal_matrix": {f"{width}|{signal}": count for (width, signal), count in sorted(matrix.items())},
            "repeat_overlap_fraction": {"minimum": min(repeat_values), "maximum": max(repeat_values), "mean": sum(repeat_values) / len(repeat_values)},
            "deterministic_artifacts": deterministic,
            "mappability": mappability,
            "amendment": policy["amendment"],
        },
    }
    write_json(output, result)


def validate_dataset(config: dict, fastq_dir: Path, simulation_manifest: Path, output: Path) -> None:
    expected_pairs = int(config["simulator"]["read_pairs_per_library"])
    read_length = int(config["simulator"]["read_length_bp"])
    samples = ("chip_rep1", "chip_rep2", "input")
    artifacts, sample_stats = [], {}
    for sample in samples:
        mates = []
        for mate in (1, 2):
            candidates = [fastq_dir / f"{sample}_{mate}.fastq", fastq_dir / f"{sample}_{mate}.fastq.gz"]
            path = next((candidate for candidate in candidates if candidate.is_file()), None)
            if path is None:
                raise FileNotFoundError(f"FASTQ missing for {sample} mate {mate}")
            count, first_id, last_id = fastq_stats(path, read_length)
            if count != expected_pairs:
                raise ValueError(f"{path}: expected {expected_pairs} reads, observed {count}")
            mates.append((count, first_id, last_id))
            artifacts.append({"role": f"{sample}_R{mate}", "path": path.name, "size_bytes": path.stat().st_size, "sha256": sha256(path)})
        if mates[0] != mates[1]:
            raise ValueError(f"paired FASTQ synchronization failure for {sample}")
        sample_stats[sample] = {"read_pairs": mates[0][0], "first_id": mates[0][1], "last_id": mates[0][2]}

    simulation = json.loads(simulation_manifest.read_text(encoding="utf-8"))
    expected_seeds = {
        "chip_rep1": int(config["simulator"]["seeds"]["replicate_1"]),
        "chip_rep2": int(config["simulator"]["seeds"]["replicate_2"]),
        "input": int(config["simulator"]["seeds"]["input"]),
    }
    if simulation.get("seeds") != expected_seeds or simulation.get("chips_version") != "v2.4":
        raise ValueError("simulation manifest mismatch")
    if artifacts[0]["sha256"] == artifacts[2]["sha256"]:
        raise ValueError("replicates are byte-identical")
    result = {
        "schema_version": "1.0",
        "type": "synthetic_broad_dataset",
        "id": config["benchmark_id"],
        "status": "SYNTHETIC_BROAD_DATASET_READY",
        "layout": "paired-end",
        "read_length_bp": read_length,
        "samples": sample_stats,
        "seeds": expected_seeds,
        "artifacts": artifacts,
        "simulation_manifest_sha256": sha256(simulation_manifest),
    }
    write_json(output, result)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    truth = sub.add_parser("truth")
    truth.add_argument("--config", required=True, type=Path)
    truth.add_argument("--primary", required=True, type=Path)
    truth.add_argument("--repeat", required=True, type=Path)
    truth.add_argument("--sam", type=Path)
    truth.add_argument("--output", required=True, type=Path)
    dataset = sub.add_parser("dataset")
    dataset.add_argument("--config", required=True, type=Path)
    dataset.add_argument("--fastq-dir", required=True, type=Path)
    dataset.add_argument("--simulation-manifest", required=True, type=Path)
    dataset.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    if args.mode == "truth":
        validate_truth(config, args.primary, args.repeat, args.sam, args.output)
    else:
        validate_dataset(config, args.fastq_dir, args.simulation_manifest, args.output)


if __name__ == "__main__":
    main()
