#!/usr/bin/env python3
import argparse
import hashlib
import json
from pathlib import Path


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", required=True)
    args = parser.parse_args()
    root = Path(args.outdir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    reference = root / "reference.fa"
    annotation = root / "annotation.gtf"
    peaks = root / "fixture.peaks.bed"
    reference.write_text(">chrStub\n" + "ACGT" * 25 + "\n", encoding="utf-8")
    annotation.write_text(
        'chrStub\tfixture\tgene\t11\t30\t.\t+\t.\tgene_id "gene1";\n'
        'chrStub\tfixture\texon\t11\t15\t.\t+\t.\tgene_id "gene1";\n'
        'chrStub\tfixture\texon\t21\t30\t.\t+\t.\tgene_id "gene1";\n',
        encoding="utf-8",
    )
    peaks.write_text(
        "chrStub\t8\t12\tpeak_promoter\n"
        "chrStub\t16\t19\tpeak_intron\n"
        "chrStub\t50\t55\tpeak_intergenic\n",
        encoding="utf-8",
    )
    peak_manifest = {
        "schema_version": "1.0", "type": "peak_calling", "id": "fixture.peaks",
        "record_id": "fixture_record", "sample_id": "fixture_sample",
        "dataset": "fixture", "experiment_id": "fixture.H3K27ac",
        "target": "H3K27ac", "genome_id": "fixture_v1", "organism": "fixture",
        "peak_type": "bed", "artifacts": {
            "peaks": {"available": True, "path": peaks.name, "sha256": sha256(peaks)}
        }, "status": "complete",
    }
    (root / "peak_manifest.json").write_text(json.dumps(peak_manifest, indent=2) + "\n", encoding="utf-8")
    reference_manifest = {
        "schema_version": "1.0", "type": "reference_bundle", "id": "fixture.reference",
        "genome_id": "fixture_v1", "build": "fixture_v1", "organism": "fixture",
        "artifacts": {"reference": {"available": True, "path": reference.name, "sha256": sha256(reference)}},
        "status": "complete",
    }
    (root / "reference_manifest.json").write_text(json.dumps(reference_manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
