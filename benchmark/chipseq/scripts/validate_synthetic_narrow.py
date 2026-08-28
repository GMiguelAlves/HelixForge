#!/usr/bin/env python3
"""Validate the frozen synthetic narrow truth or simulated FASTQ dataset."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


REQUIRED_TRUTH = (
    "narrow_true_peaks.bed",
    "narrow_true_summits.bed",
    "narrow_peak_strength.tsv",
    "narrow_negative_regions.bed",
    "narrow_mappability_probes.fa",
    "narrow_simulation_manifest.json",
)
REQUIRED_REFERENCE = (
    "synthetic_chip_v1.fa",
    "synthetic_chip_v1.fa.fai",
    "synthetic_chip_v1.repeats.bed",
    "synthetic_chip_v1.annotation.gtf",
    "reference_manifest.json",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def parse_fasta(path: Path) -> dict[str, str]:
    sequences: dict[str, list[str]] = {}
    current = None
    with path.open(encoding="ascii") as handle:
        for line in handle:
            line = line.strip()
            if line.startswith(">"):
                current = line[1:].split()[0]
                if current in sequences:
                    raise ValueError(f"duplicate FASTA sequence {current}")
                sequences[current] = []
            elif line:
                if current is None:
                    raise ValueError("FASTA sequence before header")
                sequences[current].append(line)
    return {name: "".join(parts) for name, parts in sequences.items()}


def read_bed(path: Path, minimum_columns: int) -> list[list[str]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip() or line.startswith("#"):
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) < minimum_columns:
                raise ValueError(f"{path}:{number}: expected at least {minimum_columns} columns")
            rows.append(fields)
    return rows


def intervals_overlap(left: tuple[int, int], right: tuple[int, int]) -> bool:
    return max(left[0], right[0]) < min(left[1], right[1])


def validate_sam(path: Path, expected_ids: set[str]) -> dict:
    mapped = Counter()
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("@"):
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 11:
                raise ValueError("malformed SAM record")
            query = fields[0]
            flag = int(fields[1])
            if query not in expected_ids:
                raise ValueError(f"unexpected probe {query}")
            if not flag & 4:
                mapped[query] += 1
    missing = sorted(expected_ids - set(mapped))
    non_unique = sorted(query for query, count in mapped.items() if count != 1)
    if missing or non_unique:
        raise ValueError(f"mappability failure: missing={len(missing)} non_unique={len(non_unique)}")
    return {"expected_probes": len(expected_ids), "uniquely_mapped_probes": len(mapped), "status": "PASS"}


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
            first_hash = sha256(first)
            second_hash = sha256(second)
            deterministic[f"{group}/{name}"] = first_hash
            if first_hash != second_hash:
                raise ValueError(f"non-deterministic artifact: {group}/{name}")

    sequences = parse_fasta(primary / "reference" / "synthetic_chip_v1.fa")
    ref_cfg = config["reference"]
    expected_chromosomes = {f"chrSynthetic{index}" for index in range(1, int(ref_cfg["chromosomes"]) + 1)}
    if set(sequences) != expected_chromosomes:
        raise ValueError("reference chromosome set mismatch")
    if any(len(sequence) != int(ref_cfg["chromosome_length_bp"]) for sequence in sequences.values()):
        raise ValueError("reference chromosome length mismatch")
    total_bases = sum(map(len, sequences.values()))
    total_gc = sum(sequence.count("G") + sequence.count("C") for sequence in sequences.values())
    observed_gc = total_gc / total_bases
    if abs(observed_gc - float(ref_cfg["target_gc_fraction"])) > 1e-12:
        raise ValueError(f"reference GC mismatch: {observed_gc}")

    repeats = read_bed(primary / "reference" / "synthetic_chip_v1.repeats.bed", 4)
    repeat_bases = sum(int(row[2]) - int(row[1]) for row in repeats)
    observed_repeat_fraction = repeat_bases / total_bases
    if abs(observed_repeat_fraction - float(ref_cfg["repeat_fraction"])) > 1e-12:
        raise ValueError("repeat fraction mismatch")

    peaks = read_bed(primary / "truth" / "narrow_true_peaks.bed", 6)
    summits = read_bed(primary / "truth" / "narrow_true_summits.bed", 6)
    negatives = read_bed(primary / "truth" / "narrow_negative_regions.bed", 9)
    if len(peaks) != int(config["truth"]["peak_count"]):
        raise ValueError("truth peak count mismatch")
    if len(negatives) != int(config["truth"]["negative_regions"]):
        raise ValueError("negative count mismatch")
    peak_ids = [row[3] for row in peaks]
    if len(set(peak_ids)) != len(peak_ids):
        raise ValueError("duplicate peak IDs")
    summit_by_id = {row[3]: (row[0], int(row[1])) for row in summits}
    if set(summit_by_id) != set(peak_ids):
        raise ValueError("summit IDs do not match peak IDs")

    by_chrom = defaultdict(list)
    for row in peaks:
        chrom, start, end, peak_id = row[0], int(row[1]), int(row[2]), row[3]
        if chrom not in sequences or not (0 <= start < end <= len(sequences[chrom])):
            raise ValueError(f"invalid coordinates for {peak_id}")
        if end - start != int(config["truth"]["peak_width_bp"]):
            raise ValueError(f"invalid width for {peak_id}")
        summit_chrom, summit = summit_by_id[peak_id]
        if summit_chrom != chrom or not start < summit < end:
            raise ValueError(f"invalid summit for {peak_id}")
        by_chrom[chrom].append((start, end, summit, peak_id))
    for chrom, values in by_chrom.items():
        values.sort()
        for left, right in zip(values, values[1:]):
            if intervals_overlap((left[0], left[1]), (right[0], right[1])):
                raise ValueError(f"overlapping truth peaks on {chrom}")
            if right[2] - left[2] < int(config["truth"]["minimum_summit_spacing_bp"]):
                raise ValueError(f"summit spacing violation on {chrom}")

    with (primary / "truth" / "narrow_peak_strength.tsv").open(encoding="utf-8") as handle:
        header = next(handle).rstrip("\n").split("\t")
        rows = [dict(zip(header, line.rstrip("\n").split("\t"))) for line in handle if line.strip()]
    class_counts = Counter(row["signal_class"].lower() for row in rows)
    expected_classes = {name: int(details["count"]) for name, details in config["truth"]["signal_classes"].items()}
    if class_counts != Counter(expected_classes):
        raise ValueError(f"signal class mismatch: {class_counts}")

    truth_intervals = defaultdict(list)
    for row in peaks:
        truth_intervals[row[0]].append((int(row[1]), int(row[2])))
    for row in negatives:
        chrom, start, end = row[0], int(row[1]), int(row[2])
        if chrom not in sequences or not (0 <= start < end <= len(sequences[chrom])):
            raise ValueError("invalid negative coordinates")
        if any(intervals_overlap((start, end), truth) for truth in truth_intervals[chrom]):
            raise ValueError("negative interval overlaps truth")

    expected_probe_ids = set(peak_ids) | {row[3] for row in negatives}
    mappability = {"status": "NOT_RUN"}
    if sam is not None:
        mappability = validate_sam(sam, expected_probe_ids)

    result = {
        "schema_version": "1.0",
        "status": "TRUTH_FROZEN" if mappability["status"] == "PASS" else "STRUCTURE_VALIDATED",
        "reference": {
            "id": ref_cfg["id"],
            "chromosomes": len(sequences),
            "total_bases": total_bases,
            "gc_fraction": observed_gc,
            "repeat_fraction": observed_repeat_fraction,
            "fasta_sha256": sha256(primary / "reference" / "synthetic_chip_v1.fa"),
        },
        "truth": {
            "peak_count": len(peaks),
            "negative_count": len(negatives),
            "class_counts": dict(sorted(class_counts.items())),
            "deterministic_artifacts": deterministic,
            "mappability": mappability,
        },
    }
    write_json(output, result)


def open_fastq(path: Path):
    return gzip.open(path, "rt", encoding="ascii", newline="") if path.suffix == ".gz" else path.open("r", encoding="ascii", newline="")


def fastq_stats(path: Path, expected_length: int) -> tuple[int, str, str]:
    count = 0
    first_id = last_id = ""
    with open_fastq(path) as handle:
        while True:
            name = handle.readline()
            if not name:
                break
            sequence = handle.readline().rstrip("\n\r")
            plus = handle.readline()
            quality = handle.readline().rstrip("\n\r")
            if not name.startswith("@") or not plus.startswith("+") or len(sequence) != expected_length or len(quality) != expected_length:
                raise ValueError(f"invalid FASTQ record in {path} at record {count + 1}")
            identifier = name[1:].split()[0].removesuffix("/1").removesuffix("/2")
            first_id = first_id or identifier
            last_id = identifier
            count += 1
    return count, first_id, last_id


def validate_dataset(config: dict, fastq_dir: Path, simulation_manifest: Path, output: Path) -> None:
    expected_pairs = int(config["simulator"]["read_pairs_per_library"])
    read_length = int(config["simulator"]["read_length_bp"])
    samples = ("chip_rep1", "chip_rep2", "input")
    artifacts = []
    sample_stats = {}
    for sample in samples:
        mate_stats = []
        for mate in (1, 2):
            candidates = [fastq_dir / f"{sample}_{mate}.fastq", fastq_dir / f"{sample}_{mate}.fastq.gz"]
            path = next((candidate for candidate in candidates if candidate.is_file()), None)
            if path is None:
                raise FileNotFoundError(f"FASTQ missing for {sample} mate {mate}")
            count, first_id, last_id = fastq_stats(path, read_length)
            if count != expected_pairs:
                raise ValueError(f"{path}: expected {expected_pairs} reads, observed {count}")
            mate_stats.append((count, first_id, last_id))
            artifacts.append({"role": f"{sample}_R{mate}", "path": path.name, "size_bytes": path.stat().st_size, "sha256": sha256(path)})
        if mate_stats[0] != mate_stats[1]:
            raise ValueError(f"paired FASTQ synchronization failure for {sample}")
        sample_stats[sample] = {"read_pairs": mate_stats[0][0], "first_id": mate_stats[0][1], "last_id": mate_stats[0][2]}

    simulation = json.loads(simulation_manifest.read_text(encoding="utf-8"))
    expected_seeds = {
        "chip_rep1": int(config["simulator"]["seeds"]["replicate_1"]),
        "chip_rep2": int(config["simulator"]["seeds"]["replicate_2"]),
        "input": int(config["simulator"]["seeds"]["input"]),
    }
    if simulation.get("seeds") != expected_seeds:
        raise ValueError("simulation seed manifest mismatch")
    if simulation.get("chips_version") != "v2.4":
        raise ValueError("ChIPs version mismatch")
    if artifacts[0]["sha256"] == artifacts[2]["sha256"]:
        raise ValueError("replicates are byte-identical")

    result = {
        "schema_version": "1.0",
        "type": "synthetic_narrow_dataset",
        "id": config["benchmark_id"],
        "status": "SYNTHETIC_NARROW_DATASET_READY",
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
