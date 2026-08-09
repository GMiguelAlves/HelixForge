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

    rows = []
    for replicate in (1, 2):
        record_id = f"chip_rep{replicate}"
        peak_id = f"{record_id}.H3K27ac.narrow.macs3"
        peak_dir = root / f"{peak_id}.peak_calling"
        peak_dir.mkdir(exist_ok=True)
        (peak_dir / "peaks.narrowPeak").write_text(
            f"chrStub\t{replicate * 4}\t{replicate * 4 + 8}\tp{replicate}\t100\t.\t5\t10\t8\t4\n",
            encoding="utf-8",
        )
        identity = {
            "id": peak_id, "record_id": record_id, "sample_id": record_id,
            "experiment_id": "fixture.H3K27ac", "target": "H3K27ac",
            "biological_replicate": str(replicate), "technical_replicate": "1",
            "caller": "macs3", "caller_version": "3.0.4", "peak_type": "narrow",
        }
        (root / f"{peak_id}.peak.manifest.json").write_text(
            json.dumps({"schema_version": "1.0", "type": "peak_calling", **identity}) + "\n",
            encoding="utf-8",
        )
        (root / f"{peak_id}.qc.manifest.json").write_text(
            json.dumps({"schema_version": "1.0", "type": "peak_qc_frip", **identity}) + "\n",
            encoding="utf-8",
        )
        rows.append({
            "record_id": record_id, "sample_id": record_id, "dataset": "fixture",
            "condition": "treated", "treatment": "drug", "target": "H3K27ac",
            "biological_replicate": str(replicate), "technical_replicate": "1",
            "genome_id": "fixture_v1", "organism": "fixture",
        })
    with (root / "peak_plan.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
