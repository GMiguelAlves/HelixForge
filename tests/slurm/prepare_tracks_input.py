#!/usr/bin/env python3

import argparse
import json
import shutil
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", required=True)
    parser.add_argument("--outdir", required=True)
    args = parser.parse_args()
    source = Path(args.source_dir).resolve()
    root = Path(args.outdir).resolve()
    root.mkdir(parents=True, exist_ok=True)

    reference = root / "reference.fa"
    reference.write_text(">chrTest\n" + "A" * 2000 + "\n", encoding="utf-8")
    (root / "reference_manifest.json").write_text(json.dumps({
        "schema_version": "1.0", "type": "reference_bundle", "id": "stub.reference",
        "genome_id": "stub_v1", "build": "stub_v1", "organism": "fixture",
        "status": "complete",
    }, indent=2) + "\n", encoding="utf-8")

    for record_id in ("input_rep1", "chip_rep1", "chip_rep2"):
        bam = root / f"{record_id}.filtered.bam"
        bai = root / f"{record_id}.filtered.bam.bai"
        shutil.copy2(source / bam.name, bam)
        shutil.copy2(source / bai.name, bai)
        (root / f"{record_id}.manifest.json").write_text(json.dumps({
            "schema_version": "0.1", "type": "bam_final", "id": record_id,
            "sample_id": record_id, "artifact": bam.name, "index": bai.name,
            "duplicate_policy": "all",
            "selection": {"min_mapq": 0, "include_flags": 0, "exclude_flags": 0},
            "blacklist_policy": "none", "status": "complete",
        }, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

