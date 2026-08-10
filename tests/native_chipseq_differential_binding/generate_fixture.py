#!/usr/bin/env python3
import argparse
import csv
import hashlib
import json
from pathlib import Path


def checksum(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generate(root):
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    rows = []
    for condition in ("control", "treated"):
        result_dir = root / f"fixture.{condition}.consensus_result"
        result_dir.mkdir(exist_ok=True)
        bed = result_dir / "consolidated_peaks.bed"
        bed.write_text("chrStub\t4\t12\tpeak1\nchrStub\t16\t24\tpeak2\n", encoding="utf-8")
        replicates = []
        for replicate in (1, 2):
            record_id = f"{condition}_rep{replicate}"
            sample_id = record_id
            bam = root / f"{record_id}.filtered.bam"
            bai = root / f"{record_id}.filtered.bam.bai"
            bam.write_bytes(b"stub-bam\n"); bai.write_bytes(b"stub-bai\n")
            bam_manifest = {
                "schema_version": "0.1", "type": "bam_final", "id": record_id,
                "sample_id": sample_id, "artifact": bam.name, "index": bai.name,
                "duplicate_policy": "remove", "blacklist_policy": "fragment"
            }
            (root / f"{record_id}.bam.manifest.json").write_text(json.dumps(bam_manifest) + "\n", encoding="utf-8")
            replicates.append({
                "record_id": record_id, "sample_id": sample_id, "condition": condition,
                "biological_replicate": str(replicate), "technical_replicate": "1",
                "evidence_replicate_id": str(replicate), "peak_id": f"{record_id}.peak"
            })
            rows.append({
                "record_id": record_id, "sample_id": sample_id, "dataset": "fixture",
                "condition": condition, "biological_replicate": str(replicate),
                "technical_replicate": "1", "batch": f"batch{replicate}", "layout": "paired",
                "target": "H3K27ac", "genome_id": "fixture_v1", "organism": "fixture",
            })
        manifest = {
            "schema_version": "1.0", "type": "consensus", "id": f"fixture.{condition}",
            "strategy": "union", "status": "complete", "dataset": "fixture",
            "experiment_id": "fixture.H3K27ac", "condition": condition, "target": "H3K27ac",
            "genome_id": "fixture_v1", "peak_type": "narrow", "caller": "macs3",
            "caller_version": "3.0.4", "replicate_mode": "biological",
            "replicate_policy": "require_premerged", "replicates": replicates,
            "artifacts": {"consolidated_bed": {"available": True, "path": bed.name, "sha256": checksum(bed)}}
        }
        (result_dir / "manifest.json").write_text(json.dumps(manifest) + "\n", encoding="utf-8")
        (root / f"fixture.{condition}.manifest.json").write_text(json.dumps(manifest) + "\n", encoding="utf-8")
    with (root / "peak_plan.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)
    spec = {
        "schema_version": "1.0", "provider": "deseq2", "test": "wald",
        "peak_universe": {"method": "union"},
        "counting": {"provider": "featurecounts", "unit": "fragments", "strandedness": 0,
                     "min_mapq": 0, "overlap_policy": "any", "allow_multi_overlap": False,
                     "allow_multimapping": False, "fractional": False,
                     "require_both_ends_mapped": True, "exclude_chimeric": True},
        "design": {"formula": "~ condition", "variable": "condition", "covariates": []},
        "contrasts": [
            {"id": "treated_vs_control", "factor": "condition", "numerator": "treated", "denominator": "control"},
            {"id": "control_vs_treated", "factor": "condition", "numerator": "control", "denominator": "treated"}
        ],
        "filter": {"method": "minimum_count", "min_count": 10, "min_samples": 2},
        "normalization": "deseq2_median_of_ratios",
        "parameters": {"alpha": 0.05, "lfc_threshold": 1.0, "min_replicates": 2}
    }
    (root / "db_spec.json").write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
    return root


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--outdir", required=True)
    generate(parser.parse_args().outdir)


if __name__ == "__main__": main()
