#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", required=True)
    args = parser.parse_args()
    root = Path(args.outdir).resolve(); root.mkdir(parents=True, exist_ok=True)
    (root / "reference.fa").write_text(">chrStub\nACGTACGTACGTACGT\n", encoding="utf-8")
    (root / "reference_manifest.json").write_text(json.dumps({
        "schema_version": "1.0", "type": "reference_bundle", "id": "stub.reference",
        "genome_id": "stub_v1", "build": "stub_v1", "status": "complete",
    }, indent=2) + "\n", encoding="utf-8")
    records = []
    definitions = [
        ("input_rep1", "input", "control", "1", True),
        ("chip_rep1", "H3K27ac", "treated", "1", False),
        ("chip_rep2", "H3K27ac", "treated", "2", False),
    ]
    for record_id, target, condition, replicate, is_control in definitions:
        bam = root / f"{record_id}.filtered.bam"; bai = root / f"{record_id}.filtered.bam.bai"
        bam.write_bytes(b""); bai.write_bytes(b"")
        manifest = root / f"{record_id}.manifest.json"
        manifest.write_text(json.dumps({
            "schema_version": "0.1", "type": "bam_final", "id": record_id,
            "sample_id": record_id, "artifact": bam.name, "index": bai.name,
            "duplicate_policy": "remove", "selection": {"min_mapq": 30, "include_flags": 0, "exclude_flags": 2308},
            "blacklist_policy": "fragment", "status": "complete",
        }, indent=2) + "\n", encoding="utf-8")
        records.append({
            "record_id": record_id, "sample_id": record_id, "dataset": "stub",
            "condition": condition, "target": target, "biological_replicate": replicate,
            "technical_replicate": "1", "is_control": is_control,
            "bam": bam.name, "bai": bai.name, "bam_manifest": manifest.name,
        })
    inventory = {
        "schema_version": "1.0", "type": "track_generation_input",
        "reference": {"fasta": "reference.fa", "manifest": "reference_manifest.json", "genome_id": "stub_v1", "build": "stub_v1"},
        "records": records,
    }
    (root / "tracks_input.json").write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
