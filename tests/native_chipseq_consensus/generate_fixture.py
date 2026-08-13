#!/usr/bin/env python3
import argparse
import csv
import json
import random
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", required=True)
    args = parser.parse_args()
    root = Path(args.outdir).resolve()
    root.mkdir(parents=True, exist_ok=True)

    rows = []
    generator = random.Random(20260813)
    shared_ranks = list(range(1, 601))
    for replicate in (1, 2):
        record_id = f"chip_rep{replicate}"
        peak_id = f"{record_id}.H3K27ac.narrow.macs3"
        peak_dir = root / f"{peak_id}.peak_calling"
        peak_dir.mkdir(exist_ok=True)
        ranks = shared_ranks.copy()
        for start in range(0, len(ranks), 25):
            block = ranks[start : start + 25]
            generator.shuffle(block)
            ranks[start : start + 25] = block
        peak_rows = []
        for index, rank in enumerate(ranks, 1):
            start = index * 30 + replicate - 1
            signal = 1000.0 - rank + (replicate * 0.01)
            peak_rows.append(
                f"chrStub\t{start}\t{start + 20}\tp{replicate}_{index:04d}\t100\t.\t"
                f"{signal:.2f}\t{signal / 10:.3f}\t{signal / 20:.3f}\t10\n"
            )
        (peak_dir / "peaks.narrowPeak").write_text("".join(peak_rows), encoding="utf-8")
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
