#!/usr/bin/env python3
"""Generate the frozen synthetic narrow reference and truth deterministically."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import defaultdict
from pathlib import Path


SCHEMA_VERSION = "1.0"
GENERATOR_VERSION = "synthetic-narrow-generator-v1"
LINE_WIDTH = 80
BLOCK_SIZE = 1000
REPEAT_PERIOD_BLOCKS = 10
REPEAT_TEMPLATE_COUNT = 100
EDGE_BUFFER = 2000
REPEAT_BUFFER = 2000


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def balanced_block(rng: random.Random, gc_fraction: float) -> str:
    gc_count = round(BLOCK_SIZE * gc_fraction)
    at_count = BLOCK_SIZE - gc_count
    bases = [rng.choice("GC") for _ in range(gc_count)]
    bases.extend(rng.choice("AT") for _ in range(at_count))
    rng.shuffle(bases)
    return "".join(bases)


def generate_reference(config: dict, output: Path) -> tuple[dict[str, str], list[tuple[str, int, int, str]]]:
    reference_cfg = config["reference"]
    chromosome_count = int(reference_cfg["chromosomes"])
    chromosome_length = int(reference_cfg["chromosome_length_bp"])
    gc_fraction = float(reference_cfg["target_gc_fraction"])
    seed = int(reference_cfg["seed"])
    if chromosome_length % BLOCK_SIZE:
        raise ValueError("chromosome_length_bp must be divisible by 1000")

    reference_dir = output / "reference"
    reference_dir.mkdir(parents=True, exist_ok=False)
    fasta_path = reference_dir / "synthetic_chip_v1.fa"
    fai_path = reference_dir / "synthetic_chip_v1.fa.fai"
    repeats_path = reference_dir / "synthetic_chip_v1.repeats.bed"
    annotation_path = reference_dir / "synthetic_chip_v1.annotation.gtf"
    sequences: dict[str, str] = {}
    repeats: list[tuple[str, int, int, str]] = []
    fai_rows = []

    with fasta_path.open("w", encoding="ascii", newline="\n") as fasta:
        for chromosome_index in range(1, chromosome_count + 1):
            chrom = f"chrSynthetic{chromosome_index}"
            rng = random.Random(seed + chromosome_index)
            repeat_rng = random.Random(seed + 1000 + chromosome_index)
            templates = [balanced_block(repeat_rng, gc_fraction) for _ in range(REPEAT_TEMPLATE_COUNT)]
            blocks = []
            for block_index in range(chromosome_length // BLOCK_SIZE):
                if block_index % REPEAT_PERIOD_BLOCKS == REPEAT_PERIOD_BLOCKS // 2:
                    template_index = (block_index // REPEAT_PERIOD_BLOCKS) % REPEAT_TEMPLATE_COUNT
                    block = templates[template_index]
                    start = block_index * BLOCK_SIZE
                    repeats.append((chrom, start, start + BLOCK_SIZE, f"repeat_{chromosome_index}_{block_index:05d}"))
                else:
                    block = balanced_block(rng, gc_fraction)
                blocks.append(block)
            sequence = "".join(blocks)
            if len(sequence) != chromosome_length:
                raise AssertionError("reference length mismatch")
            sequences[chrom] = sequence
            fasta.write(f">{chrom}\n")
            sequence_offset = fasta.tell()
            for start in range(0, chromosome_length, LINE_WIDTH):
                fasta.write(sequence[start : start + LINE_WIDTH] + "\n")
            fai_rows.append((chrom, chromosome_length, sequence_offset, LINE_WIDTH, LINE_WIDTH + 1))

    with fai_path.open("w", encoding="ascii", newline="\n") as handle:
        for row in fai_rows:
            handle.write("\t".join(map(str, row)) + "\n")

    with repeats_path.open("w", encoding="ascii", newline="\n") as handle:
        for row in repeats:
            handle.write("\t".join(map(str, row)) + "\n")

    with annotation_path.open("w", encoding="ascii", newline="\n") as handle:
        for index, chrom in enumerate(sorted(sequences), 1):
            handle.write(
                f'{chrom}\tHelixForge\tgene\t100001\t110000\t.\t+\t.\t'
                f'gene_id "synthetic_gene_{index}"; gene_name "SYNTHETIC_GENE_{index}";\n'
            )

    return sequences, repeats


def complement_segments(chromosome_length: int, repeats: list[tuple[int, int]]) -> list[tuple[int, int]]:
    blocked = []
    for start, end in repeats:
        blocked.append((max(EDGE_BUFFER, start - REPEAT_BUFFER), min(chromosome_length - EDGE_BUFFER, end + REPEAT_BUFFER)))
    blocked.sort()
    merged = []
    for start, end in blocked:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    eligible = []
    cursor = EDGE_BUFFER
    for start, end in merged:
        if cursor < start:
            eligible.append((cursor, start))
        cursor = max(cursor, end)
    if cursor < chromosome_length - EDGE_BUFFER:
        eligible.append((cursor, chromosome_length - EDGE_BUFFER))
    return eligible


def gc_fraction(sequence: str) -> float:
    return (sequence.count("G") + sequence.count("C")) / len(sequence)


def candidate_intervals(
    sequences: dict[str, str], repeats: list[tuple[str, int, int, str]], peak_width: int, seed: int
) -> list[dict]:
    by_chrom: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for chrom, start, end, _name in repeats:
        by_chrom[chrom].append((start, end))
    candidates = []
    half = peak_width // 2
    for chrom_index, chrom in enumerate(sorted(sequences), 1):
        sequence = sequences[chrom]
        rng = random.Random(seed + 2000 + chrom_index)
        for segment_index, (left, right) in enumerate(complement_segments(len(sequence), by_chrom[chrom])):
            low = left + half
            high = right - half - 1
            if high < low:
                continue
            summit = rng.randint(low, high)
            start = summit - half
            end = start + peak_width
            candidates.append(
                {
                    "chrom": chrom,
                    "start": start,
                    "end": end,
                    "summit": summit,
                    "gc_fraction": gc_fraction(sequence[start:end]),
                    "segment_index": segment_index,
                }
            )
    ranked = sorted(range(len(candidates)), key=lambda idx: (candidates[idx]["gc_fraction"], candidates[idx]["chrom"], candidates[idx]["start"]))
    for rank, index in enumerate(ranked):
        candidates[index]["gc_decile"] = min(9, rank * 10 // len(candidates))
    return candidates


def separated(candidate: dict, selected: list[dict], distance: int) -> bool:
    return all(
        other["chrom"] != candidate["chrom"] or abs(other["summit"] - candidate["summit"]) >= distance
        for other in selected
    )


def generate_truth(config: dict, sequences: dict[str, str], repeats: list[tuple[str, int, int, str]], output: Path) -> None:
    truth_cfg = config["truth"]
    reference_seed = int(config["reference"]["seed"])
    peak_count = int(truth_cfg["peak_count"])
    peak_width = int(truth_cfg["peak_width_bp"])
    minimum_spacing = int(truth_cfg["minimum_summit_spacing_bp"])
    candidates = candidate_intervals(sequences, repeats, peak_width, reference_seed)
    chooser = random.Random(reference_seed + 3000)
    shuffled = candidates[:]
    chooser.shuffle(shuffled)
    selected = []
    for candidate in shuffled:
        if separated(candidate, selected, minimum_spacing):
            selected.append(candidate)
        if len(selected) == peak_count:
            break
    if len(selected) != peak_count:
        raise RuntimeError(f"could select only {len(selected)} truth peaks")

    labels = []
    for name, details in truth_cfg["signal_classes"].items():
        labels.extend([(name.upper(), float(details["score"]))] * int(details["count"]))
    if len(labels) != peak_count:
        raise ValueError("signal-class counts do not equal peak_count")
    chooser.shuffle(labels)
    selected.sort(key=lambda row: (row["chrom"], row["start"]))
    for index, (candidate, (label, score)) in enumerate(zip(selected, labels), 1):
        candidate.update(peak_id=f"NARROW_{index:04d}", signal_class=label, signal_strength=score)

    negative_count = int(truth_cfg["negative_regions"])
    truth_keys = {(row["chrom"], row["segment_index"]) for row in selected}
    available: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for candidate in candidates:
        key = (candidate["chrom"], candidate["segment_index"])
        if key in truth_keys:
            continue
        if not separated(candidate, selected, 2000):
            continue
        available[(candidate["chrom"], candidate["gc_decile"])].append(candidate)
    for values in available.values():
        values.sort(key=lambda row: (row["gc_fraction"], row["start"]))

    negatives = []
    for truth in selected:
        key = (truth["chrom"], truth["gc_decile"])
        pool = available[key]
        if not pool:
            raise RuntimeError(f"no matched negative candidate for {truth['peak_id']} in {key}")
        chosen_index = min(range(len(pool)), key=lambda idx: (abs(pool[idx]["gc_fraction"] - truth["gc_fraction"]), pool[idx]["start"]))
        negative = pool.pop(chosen_index)
        negative["negative_id"] = f"NEGATIVE_{len(negatives) + 1:04d}"
        negative["matched_peak_id"] = truth["peak_id"]
        negatives.append(negative)
        if len(negatives) == negative_count:
            break
    if len(negatives) != negative_count:
        raise RuntimeError("negative panel size mismatch")
    negatives.sort(key=lambda row: (row["chrom"], row["start"]))

    truth_dir = output / "truth"
    truth_dir.mkdir(parents=True, exist_ok=False)
    peaks_path = truth_dir / "narrow_true_peaks.bed"
    summits_path = truth_dir / "narrow_true_summits.bed"
    strength_path = truth_dir / "narrow_peak_strength.tsv"
    negatives_path = truth_dir / "narrow_negative_regions.bed"
    probes_path = truth_dir / "narrow_mappability_probes.fa"

    with peaks_path.open("w", encoding="ascii", newline="\n") as peaks, summits_path.open("w", encoding="ascii", newline="\n") as summits:
        for row in selected:
            peaks.write(f"{row['chrom']}\t{row['start']}\t{row['end']}\t{row['peak_id']}\t{row['signal_strength']:.2f}\t.\n")
            summits.write(f"{row['chrom']}\t{row['summit']}\t{row['summit'] + 1}\t{row['peak_id']}\t{row['signal_strength']:.2f}\t.\n")
    with strength_path.open("w", encoding="ascii", newline="\n") as handle:
        handle.write("peak_id\tchrom\tstart\tend\tsummit\tsignal_class\tsignal_strength\tgc_fraction\tgc_decile\tmappability\tseed\n")
        for row in selected:
            handle.write(
                f"{row['peak_id']}\t{row['chrom']}\t{row['start']}\t{row['end']}\t{row['summit']}\t"
                f"{row['signal_class']}\t{row['signal_strength']:.2f}\t{row['gc_fraction']:.6f}\t{row['gc_decile']}\t"
                f"pending_bowtie2_probe\t{reference_seed}\n"
            )
    with negatives_path.open("w", encoding="ascii", newline="\n") as handle:
        for row in negatives:
            handle.write(
                f"{row['chrom']}\t{row['start']}\t{row['end']}\t{row['negative_id']}\t0\t.\t"
                f"{row['matched_peak_id']}\t{row['gc_fraction']:.6f}\t{row['gc_decile']}\n"
            )
    with probes_path.open("w", encoding="ascii", newline="\n") as handle:
        for row in selected + negatives:
            identifier = row.get("peak_id", row.get("negative_id"))
            start = row["summit"] - 37
            probe = sequences[row["chrom"]][start : start + 75]
            handle.write(f">{identifier}\n{probe}\n")


def build_manifests(config: dict, output: Path) -> None:
    reference_dir = output / "reference"
    truth_dir = output / "truth"
    fasta = reference_dir / "synthetic_chip_v1.fa"
    repeat_bed = reference_dir / "synthetic_chip_v1.repeats.bed"
    annotation = reference_dir / "synthetic_chip_v1.annotation.gtf"
    fai = reference_dir / "synthetic_chip_v1.fa.fai"
    reference_manifest = {
        "schema_version": SCHEMA_VERSION,
        "type": "synthetic_reference",
        "id": config["reference"]["id"],
        "assembly": config["reference"]["id"],
        "generator": GENERATOR_VERSION,
        "seed": config["reference"]["seed"],
        "chromosomes": config["reference"]["chromosomes"],
        "chromosome_length_bp": config["reference"]["chromosome_length_bp"],
        "total_size_bp": config["reference"]["chromosomes"] * config["reference"]["chromosome_length_bp"],
        "effective_genome_size": config["reference"]["effective_genome_size"],
        "target_gc_fraction": config["reference"]["target_gc_fraction"],
        "repeat_model": {
            "block_size_bp": BLOCK_SIZE,
            "period_blocks": REPEAT_PERIOD_BLOCKS,
            "template_count_per_chromosome": REPEAT_TEMPLATE_COUNT,
            "fraction": config["reference"]["repeat_fraction"],
        },
        "artifacts": {
            "fasta": {"path": fasta.name, "size_bytes": fasta.stat().st_size, "sha256": sha256(fasta)},
            "fai": {"path": fai.name, "size_bytes": fai.stat().st_size, "sha256": sha256(fai)},
            "annotation": {"path": annotation.name, "size_bytes": annotation.stat().st_size, "sha256": sha256(annotation)},
            "repeats": {"path": repeat_bed.name, "size_bytes": repeat_bed.stat().st_size, "sha256": sha256(repeat_bed)},
        },
        "status": "prepared",
    }
    write_json(reference_dir / "reference_manifest.json", reference_manifest)

    truth_artifacts = {}
    for path in sorted(truth_dir.iterdir()):
        if path.name == "narrow_simulation_manifest.json":
            continue
        truth_artifacts[path.name] = {"size_bytes": path.stat().st_size, "sha256": sha256(path)}
    truth_manifest = {
        "schema_version": SCHEMA_VERSION,
        "type": "synthetic_narrow_truth",
        "id": config["benchmark_id"] + ".truth",
        "generator": GENERATOR_VERSION,
        "reference_id": config["reference"]["id"],
        "reference_sha256": reference_manifest["artifacts"]["fasta"]["sha256"],
        "seed": config["reference"]["seed"],
        "peak_count": config["truth"]["peak_count"],
        "negative_count": config["truth"]["negative_regions"],
        "peak_width_bp": config["truth"]["peak_width_bp"],
        "minimum_summit_spacing_bp": config["truth"]["minimum_summit_spacing_bp"],
        "signal_classes": config["truth"]["signal_classes"],
        "mappability_status": "pending_bowtie2_probe",
        "artifacts": truth_artifacts,
        "status": "prepared",
    }
    write_json(truth_dir / "narrow_simulation_manifest.json", truth_manifest)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    sequences, repeats = generate_reference(config, output)
    generate_truth(config, sequences, repeats, output)
    build_manifests(config, output)
    print(json.dumps({"status": "PREPARED", "output": str(output), "generator": GENERATOR_VERSION}, sort_keys=True))


if __name__ == "__main__":
    main()
