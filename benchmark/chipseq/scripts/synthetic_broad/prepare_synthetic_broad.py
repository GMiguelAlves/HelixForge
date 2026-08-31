#!/usr/bin/env python3
"""Generate the amended frozen synthetic broad reference and truth."""

from __future__ import annotations

import argparse
import bisect
import importlib.util
import json
import random
from collections import Counter, defaultdict
from pathlib import Path


GENERATOR_VERSION = "synthetic-broad-generator-v1"
SCHEMA_VERSION = "1.0"
MAX_PLACEMENT_ATTEMPTS = 500_000


def load_reference_generator():
    path = Path(__file__).resolve().parent.parent / "synthetic_narrow" / "prepare_synthetic_narrow.py"
    spec = importlib.util.spec_from_file_location("synthetic_reference_generator", path)
    if not spec or not spec.loader:
        raise ImportError(f"cannot load shared reference generator: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


REFERENCE = load_reference_generator()
sha256 = REFERENCE.sha256
write_json = REFERENCE.write_json
generate_reference = REFERENCE.generate_reference


def gc_fraction(sequence: str) -> float:
    return (sequence.count("G") + sequence.count("C")) / len(sequence)


def repeat_index(repeats: list[tuple[str, int, int, str]], buffer_bp: int) -> tuple[dict[str, list[tuple[int, int]]], dict[str, list[int]]]:
    expanded: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for chrom, start, end, _name in repeats:
        expanded[chrom].append((start - buffer_bp, end + buffer_bp))
    starts = {}
    for chrom, rows in expanded.items():
        rows.sort()
        starts[chrom] = [row[0] for row in rows]
    return dict(expanded), starts


def boundary_eligible(position: int, expanded: list[tuple[int, int]], starts: list[int], chromosome_length: int, edge_buffer: int) -> bool:
    if position < edge_buffer or position > chromosome_length - edge_buffer:
        return False
    index = bisect.bisect_right(starts, position) - 1
    if index >= 0:
        left, right = expanded[index]
        if left < position < right:
            return False
    return True


def repeat_overlap(start: int, end: int, repeats: list[tuple[int, int]]) -> int:
    return sum(max(0, min(end, right) - max(start, left)) for left, right in repeats if left < end and right > start)


def separated(start: int, end: int, intervals: list[tuple[int, int]], gap: int) -> bool:
    return all(end + gap <= left or start >= right + gap for left, right in intervals)


def absolute_gc_decile(value: float) -> int:
    return min(9, max(0, int(value * 10)))


def make_specs(config: dict) -> list[dict]:
    truth = config["truth"]
    seed = int(config["reference"]["seed"])
    count = int(truth["domains_per_width_strength_cell"])
    width_rng = random.Random(seed + 4000)
    order_rng = random.Random(seed + 4001)
    specs = []
    for width_name, bounds in truth["width_classes_bp"].items():
        for signal_name, strength in truth["signal_classes"].items():
            for _ in range(count):
                specs.append(
                    {
                        "width_class": width_name.upper(),
                        "signal_class": signal_name.upper(),
                        "signal_strength": float(strength),
                        "width": width_rng.randint(int(bounds[0]), int(bounds[1])),
                    }
                )
    if len(specs) != int(truth["domain_count"]):
        raise ValueError("width-by-signal design does not equal domain_count")
    order_rng.shuffle(specs)
    return specs


def place_truth(config: dict, sequences: dict[str, str], repeats: list[tuple[str, int, int, str]]) -> list[dict]:
    truth = config["truth"]
    policy = truth["repeat_traversal"]
    if not policy.get("interior_allowed") or not policy.get("require_both_boundaries_eligible"):
        raise ValueError("approved repeat-traversal amendment is not active")
    buffer_bp = int(policy["boundary_buffer_bp"])
    edge_buffer = 2000
    minimum_gap = int(truth["minimum_inter_domain_gap_bp"])
    expanded, expanded_starts = repeat_index(repeats, buffer_bp)
    raw_repeats: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for chrom, start, end, _name in repeats:
        raw_repeats[chrom].append((start, end))

    rng = random.Random(int(config["reference"]["seed"]) + 5000)
    chromosomes = sorted(sequences)
    occupied: dict[str, list[tuple[int, int]]] = defaultdict(list)
    selected = []
    for spec in make_specs(config):
        for _attempt in range(MAX_PLACEMENT_ATTEMPTS):
            chrom = rng.choice(chromosomes)
            width = int(spec["width"])
            start = rng.randint(edge_buffer, len(sequences[chrom]) - edge_buffer - width)
            end = start + width
            if not boundary_eligible(start, expanded[chrom], expanded_starts[chrom], len(sequences[chrom]), edge_buffer):
                continue
            if not boundary_eligible(end, expanded[chrom], expanded_starts[chrom], len(sequences[chrom]), edge_buffer):
                continue
            if not separated(start, end, occupied[chrom], minimum_gap):
                continue
            overlap = repeat_overlap(start, end, raw_repeats[chrom])
            sequence = sequences[chrom][start:end]
            selected.append(
                {
                    **spec,
                    "chrom": chrom,
                    "start": start,
                    "end": end,
                    "gc_fraction": gc_fraction(sequence),
                    "gc_decile": absolute_gc_decile(gc_fraction(sequence)),
                    "repeat_overlap_bp": overlap,
                    "repeat_overlap_fraction": overlap / width,
                }
            )
            occupied[chrom].append((start, end))
            break
        else:
            raise RuntimeError(f"unable to place broad domain after {MAX_PLACEMENT_ATTEMPTS} attempts: {spec}")

    selected.sort(key=lambda row: (row["chrom"], row["start"], row["end"]))
    for index, row in enumerate(selected, 1):
        row["domain_id"] = f"BROAD_{index:04d}"
    return selected


def place_negatives(config: dict, sequences: dict[str, str], repeats: list[tuple[str, int, int, str]], truth_rows: list[dict]) -> list[dict]:
    truth = config["truth"]
    policy = truth["repeat_traversal"]
    buffer_bp = int(policy["boundary_buffer_bp"])
    edge_buffer = 2000
    expanded, expanded_starts = repeat_index(repeats, buffer_bp)
    raw_repeats: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for chrom, start, end, _name in repeats:
        raw_repeats[chrom].append((start, end))
    occupied: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for row in truth_rows:
        occupied[row["chrom"]].append((row["start"], row["end"]))

    rng = random.Random(int(config["reference"]["seed"]) + 6000)
    negatives = []
    for truth_row in truth_rows:
        chrom = truth_row["chrom"]
        width = int(truth_row["width"])
        for _attempt in range(MAX_PLACEMENT_ATTEMPTS):
            start = rng.randint(edge_buffer, len(sequences[chrom]) - edge_buffer - width)
            end = start + width
            if not boundary_eligible(start, expanded[chrom], expanded_starts[chrom], len(sequences[chrom]), edge_buffer):
                continue
            if not boundary_eligible(end, expanded[chrom], expanded_starts[chrom], len(sequences[chrom]), edge_buffer):
                continue
            if not separated(start, end, occupied[chrom], 2000):
                continue
            sequence = sequences[chrom][start:end]
            candidate_gc = gc_fraction(sequence)
            if absolute_gc_decile(candidate_gc) != truth_row["gc_decile"]:
                continue
            overlap = repeat_overlap(start, end, raw_repeats[chrom])
            negative = {
                "negative_id": f"BROAD_NEGATIVE_{len(negatives) + 1:04d}",
                "matched_domain_id": truth_row["domain_id"],
                "chrom": chrom,
                "start": start,
                "end": end,
                "width": width,
                "gc_fraction": candidate_gc,
                "gc_decile": absolute_gc_decile(candidate_gc),
                "repeat_overlap_bp": overlap,
                "repeat_overlap_fraction": overlap / width,
            }
            negatives.append(negative)
            occupied[chrom].append((start, end))
            break
        else:
            raise RuntimeError(f"unable to place matched negative for {truth_row['domain_id']}")
    return sorted(negatives, key=lambda row: (row["chrom"], row["start"], row["end"]))


def write_truth(config: dict, sequences: dict[str, str], truth_rows: list[dict], negatives: list[dict], output: Path) -> None:
    truth_dir = output / "truth"
    truth_dir.mkdir(parents=True, exist_ok=False)
    domains_path = truth_dir / "broad_true_domains.bed"
    strength_path = truth_dir / "broad_domain_strength.tsv"
    negatives_path = truth_dir / "broad_negative_regions.bed"
    probes_path = truth_dir / "broad_boundary_mappability_probes.fa"

    with domains_path.open("w", encoding="ascii", newline="\n") as handle:
        for row in truth_rows:
            handle.write(f"{row['chrom']}\t{row['start']}\t{row['end']}\t{row['domain_id']}\t{row['signal_strength']:.2f}\t.\n")
    with strength_path.open("w", encoding="ascii", newline="\n") as handle:
        handle.write(
            "domain_id\tchrom\tstart\tend\twidth\twidth_class\tsignal_class\tsignal_strength\t"
            "gc_fraction\tgc_decile\trepeat_overlap_bp\trepeat_overlap_fraction\tboundary_mappability\tseed\n"
        )
        for row in truth_rows:
            handle.write(
                f"{row['domain_id']}\t{row['chrom']}\t{row['start']}\t{row['end']}\t{row['width']}\t"
                f"{row['width_class']}\t{row['signal_class']}\t{row['signal_strength']:.2f}\t"
                f"{row['gc_fraction']:.6f}\t{row['gc_decile']}\t{row['repeat_overlap_bp']}\t"
                f"{row['repeat_overlap_fraction']:.8f}\tpending_bowtie2_boundary_probes\t{config['reference']['seed']}\n"
            )
    with negatives_path.open("w", encoding="ascii", newline="\n") as handle:
        for row in negatives:
            handle.write(
                f"{row['chrom']}\t{row['start']}\t{row['end']}\t{row['negative_id']}\t0\t.\t"
                f"{row['matched_domain_id']}\t{row['width']}\t{row['gc_fraction']:.6f}\t{row['gc_decile']}\t"
                f"{row['repeat_overlap_bp']}\t{row['repeat_overlap_fraction']:.8f}\n"
            )
    with probes_path.open("w", encoding="ascii", newline="\n") as handle:
        for row in [*truth_rows, *negatives]:
            identifier = row.get("domain_id", row.get("negative_id"))
            sequence = sequences[row["chrom"]]
            handle.write(f">{identifier}__LEFT\n{sequence[row['start']:row['start'] + 75]}\n")
            handle.write(f">{identifier}__RIGHT\n{sequence[row['end'] - 75:row['end']]}\n")


def build_manifests(config: dict, output: Path, truth_rows: list[dict], negatives: list[dict]) -> None:
    reference_dir = output / "reference"
    truth_dir = output / "truth"
    fasta = reference_dir / "synthetic_chip_v1.fa"
    reference_manifest = {
        "schema_version": SCHEMA_VERSION,
        "type": "synthetic_reference",
        "id": config["reference"]["id"],
        "assembly": config["reference"]["id"],
        "generator": REFERENCE.GENERATOR_VERSION,
        "seed": config["reference"]["seed"],
        "chromosomes": config["reference"]["chromosomes"],
        "chromosome_length_bp": config["reference"]["chromosome_length_bp"],
        "total_size_bp": config["reference"]["chromosomes"] * config["reference"]["chromosome_length_bp"],
        "effective_genome_size": config["reference"]["effective_genome_size"],
        "target_gc_fraction": config["reference"]["target_gc_fraction"],
        "repeat_model": {
            "block_size_bp": REFERENCE.BLOCK_SIZE,
            "period_blocks": REFERENCE.REPEAT_PERIOD_BLOCKS,
            "template_count_per_chromosome": REFERENCE.REPEAT_TEMPLATE_COUNT,
            "fraction": config["reference"]["repeat_fraction"],
        },
        "artifacts": {},
        "status": "prepared",
    }
    for role, name in {
        "fasta": "synthetic_chip_v1.fa",
        "fai": "synthetic_chip_v1.fa.fai",
        "annotation": "synthetic_chip_v1.annotation.gtf",
        "repeats": "synthetic_chip_v1.repeats.bed",
    }.items():
        path = reference_dir / name
        reference_manifest["artifacts"][role] = {"path": name, "size_bytes": path.stat().st_size, "sha256": sha256(path)}
    write_json(reference_dir / "reference_manifest.json", reference_manifest)

    artifacts = {}
    for path in sorted(truth_dir.iterdir()):
        if path.name != "broad_simulation_manifest.json":
            artifacts[path.name] = {"size_bytes": path.stat().st_size, "sha256": sha256(path)}
    matrix = Counter((row["width_class"], row["signal_class"]) for row in truth_rows)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "type": "synthetic_broad_truth",
        "id": config["benchmark_id"] + ".truth",
        "generator": GENERATOR_VERSION,
        "reference_id": config["reference"]["id"],
        "reference_sha256": sha256(fasta),
        "seed": config["reference"]["seed"],
        "domain_count": len(truth_rows),
        "negative_count": len(negatives),
        "minimum_inter_domain_gap_bp": config["truth"]["minimum_inter_domain_gap_bp"],
        "width_classes_bp": config["truth"]["width_classes_bp"],
        "signal_classes": config["truth"]["signal_classes"],
        "width_signal_matrix": {f"{width}|{signal}": count for (width, signal), count in sorted(matrix.items())},
        "repeat_traversal": config["truth"]["repeat_traversal"],
        "repeat_overlap_summary": {
            "truth_bases": sum(row["repeat_overlap_bp"] for row in truth_rows),
            "negative_bases": sum(row["repeat_overlap_bp"] for row in negatives),
        },
        "mappability_status": "pending_bowtie2_boundary_probes",
        "artifacts": artifacts,
        "status": "prepared",
    }
    write_json(truth_dir / "broad_simulation_manifest.json", manifest)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    sequences, repeats = generate_reference(config, output)
    truth_rows = place_truth(config, sequences, repeats)
    negatives = place_negatives(config, sequences, repeats, truth_rows)
    write_truth(config, sequences, truth_rows, negatives, output)
    build_manifests(config, output, truth_rows, negatives)
    print(json.dumps({"status": "PREPARED", "output": str(output), "generator": GENERATOR_VERSION}, sort_keys=True))


if __name__ == "__main__":
    main()
