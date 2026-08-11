#!/usr/bin/env python3

import argparse
import csv
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-plan", required=True)
    parser.add_argument("--outdir", required=True)
    args = parser.parse_args()

    outdir = Path(args.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    reference = outdir / "reference.fa"
    reference.write_text(">chrTest\n" + "A" * 2000 + "\n", encoding="utf-8")

    with open(args.source_plan, encoding="utf-8", newline="") as handle:
        rows = [row for row in csv.DictReader(handle, delimiter="\t") if row["record_id"].startswith("chip_")]
    if len(rows) != 2:
        raise ValueError(f"expected two treatment rows, found {len(rows)}")
    fields = list(rows[0])
    for field in ("genome_fasta", "blacklist_bed"):
        if field not in fields:
            fields.append(field)
    for row in rows:
        row["genome_fasta"] = str(reference)
        row["blacklist_bed"] = ""
    with (outdir / "peak_plan.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()

