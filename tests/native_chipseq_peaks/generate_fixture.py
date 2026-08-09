#!/usr/bin/env python3
import argparse
import csv
import hashlib
import json
import subprocess
from pathlib import Path


SEQ = "A" * 30
QUAL = "I" * 30


def pair(name, start):
    mate = start + 50
    return [
        f"{name}\t99\tchrTest\t{start}\t60\t30M\t=\t{mate}\t80\t{SEQ}\t{QUAL}",
        f"{name}\t147\tchrTest\t{mate}\t60\t30M\t=\t{start}\t-80\t{SEQ}\t{QUAL}",
    ]


def write_bam(root, record_id, cluster, background=30, extra=0):
    sam = root / f"{record_id}.sam"
    lines = ["@HD\tVN:1.6\tSO:unsorted", "@SQ\tSN:chrTest\tLN:2000"]
    if cluster is None:
        starts = [20 + ((index * 23) % 1900) for index in range(100 + extra)]
    else:
        starts = [cluster + (index % 35) for index in range(140 + extra)]
        starts += [30 + ((index * 61) % 1850) for index in range(background)]
    for index, start in enumerate(starts):
        lines.extend(pair(f"{record_id}_{index:04d}", start))
    sam.write_text("\n".join(lines) + "\n", encoding="utf-8")
    unsorted = root / f"{record_id}.unsorted.bam"
    bam = root / f"{record_id}.filtered.bam"
    subprocess.run(["samtools", "view", "-b", "-o", unsorted, sam], check=True)
    subprocess.run(["samtools", "sort", "-o", bam, unsorted], check=True)
    subprocess.run(["samtools", "index", bam], check=True)
    sam.unlink()
    unsorted.unlink()
    return bam


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--treatment-extra", type=int, default=0)
    parser.add_argument("--control-extra", type=int, default=0)
    args = parser.parse_args()
    root = Path(args.outdir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    records = {
        "input_rep1": write_bam(root, "input_rep1", None, extra=args.control_extra),
        "chip_rep1": write_bam(root, "chip_rep1", 250, extra=args.treatment_extra),
        "chip_rep2": write_bam(root, "chip_rep2", 850),
    }
    for record_id, bam in records.items():
        manifest = {
            "schema_version": "0.1", "type": "bam_final", "id": record_id,
            "reference_sha256": "fixture-reference-sha256", "sha256": digest(bam),
        }
        (root / f"{record_id}.manifest.json").write_text(
            json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8"
        )

    fields = [
        "record_id", "sample_id", "dataset", "condition", "biological_replicate",
        "technical_replicate", "layout", "single_end", "is_control", "control_id",
        "target", "genome_id", "organism", "blacklist_bed", "peak_dir", "peak_caller",
        "peak_type", "macs_qvalue", "macs_pvalue", "macs_genome_size", "macs_extra_opts",
    ]
    rows = [
        ["input_rep1", "input_rep1", "fixture", "control", "1", "1", "paired", "false", "true", "", "input", "fixture_v1", "fixture", "", str(root / "peaks"), "macs3", "narrow", "0.5", "", "1800", ""],
        ["chip_rep1", "chip_rep1", "fixture", "treated", "1", "1", "paired", "false", "false", "input_rep1", "H3K27ac", "fixture_v1", "fixture", "", str(root / "peaks"), "macs3", "narrow", "0.5", "", "1800", "--nomodel"],
        ["chip_rep2", "chip_rep2", "fixture", "treated", "2", "1", "paired", "false", "false", "input_rep1", "H3K27ac", "fixture_v1", "fixture", "", str(root / "peaks"), "macs3", "narrow", "0.5", "", "1800", "--nomodel"],
    ]
    with (root / "chipseq_plan.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(fields)
        writer.writerows(rows)


if __name__ == "__main__":
    main()
