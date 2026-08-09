#!/usr/bin/env python3
import argparse
import csv
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", required=True)
    args = parser.parse_args()
    root = Path(args.outdir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    reference = root / "reference.fa"
    blacklist = root / "blacklist.bed"
    reference.write_text(">chrStub\n" + "A" * 100 + "\n", encoding="utf-8")
    blacklist.write_text("chrStub\t90\t95\n", encoding="utf-8")

    rows = []
    for replicate in (1, 2):
        record_id = f"chip_rep{replicate}"
        peak_id = f"{record_id}.H3K27ac.narrow.macs3"
        bam = root / f"{record_id}.filtered.bam"
        bai = root / f"{record_id}.filtered.bam.bai"
        bam.write_bytes(b"stub-bam\n")
        bai.write_bytes(b"stub-bai\n")
        (root / f"{record_id}.bam.manifest.json").write_text(json.dumps({
            "schema_version": "0.1", "type": "bam_final", "id": record_id,
            "duplicate_policy": "remove", "selection": {"min_mapq": 30, "include_flags": 0, "exclude_flags": 2308},
            "blacklist_policy": "fragment",
        }) + "\n", encoding="utf-8")
        peak_dir = root / f"{peak_id}.peak_calling"
        peak_dir.mkdir(exist_ok=True)
        (peak_dir / "peaks.narrowPeak").write_text(
            f"chrStub\t{replicate * 10}\t{replicate * 10 + 8}\tp{replicate}\t100\t.\t5\t10\t8\t4\n",
            encoding="utf-8",
        )
        (root / f"{peak_id}.manifest.json").write_text(json.dumps({
            "schema_version": "1.0", "type": "peak_calling", "id": peak_id,
            "record_id": record_id, "sample_id": record_id,
            "experiment_id": "fixture.H3K27ac", "target": "H3K27ac",
            "biological_replicate": str(replicate), "technical_replicate": "1",
            "control_id": "input_rep1", "control_record_id": "input_rep1",
            "caller": "macs3", "caller_version": "3.0.4", "peak_type": "narrow",
        }) + "\n", encoding="utf-8")
        rows.append({
            "record_id": record_id, "sample_id": record_id, "dataset": "fixture",
            "condition": "treated", "biological_replicate": str(replicate),
            "technical_replicate": "1", "layout": "paired", "single_end": "false",
            "is_control": "false", "control_id": "input_rep1", "target": "H3K27ac",
            "genome_id": "fixture_v1", "organism": "fixture",
            "genome_fasta": str(reference), "blacklist_bed": str(blacklist),
        })
    with (root / "peak_plan.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
