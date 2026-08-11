#!/usr/bin/env python3

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


SEQ = "ACGT"
QUAL = "IIII"


def pair(name, start):
    mate = start + 3
    return [
        f"{name}\t99\tchrStub\t{start}\t60\t4M\t=\t{mate}\t7\t{SEQ}\t{QUAL}",
        f"{name}\t147\tchrStub\t{mate}\t60\t4M\t=\t{start}\t-7\t{SEQ}\t{QUAL}",
    ]


def write_bam(root, record_id, starts, counts):
    sam = root / f"{record_id}.sam"
    lines = ["@HD\tVN:1.6\tSO:unsorted", "@SQ\tSN:chrStub\tLN:1000"]
    index = 0
    for count, start in zip(counts, starts):
        for _ in range(count):
            lines.extend(pair(f"{record_id}_{index:04d}", start))
            index += 1
    sam.write_text("\n".join(lines) + "\n", encoding="utf-8")
    unsorted = root / f"{record_id}.unsorted.bam"
    bam = root / f"{record_id}.filtered.bam"
    subprocess.run(["samtools", "view", "-b", "-o", unsorted, sam], check=True)
    subprocess.run(["samtools", "sort", "-o", bam, unsorted], check=True)
    subprocess.run(["samtools", "index", bam], check=True)
    subprocess.run(["samtools", "quickcheck", bam], check=True)
    sam.unlink()
    unsorted.unlink()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", required=True)
    args = parser.parse_args()
    root = Path(args.outdir).resolve()
    bed_starts = [10 + index * 20 for index in range(30)]
    sam_starts = [start + 1 for start in bed_starts]
    bed_text = "".join(
        f"chrStub\t{start}\t{start + 10}\tpeak{index + 1}\n"
        for index, start in enumerate(bed_starts)
    )
    for condition in ("control", "treated"):
        result_dir = root / f"fixture.{condition}.consensus_result"
        bed = result_dir / "consolidated_peaks.bed"
        bed.write_text(bed_text, encoding="utf-8")
        digest = hashlib.sha256(bed.read_bytes()).hexdigest()
        for manifest_path in (result_dir / "manifest.json", root / f"fixture.{condition}.manifest.json"):
            document = json.loads(manifest_path.read_text())
            document["artifacts"]["consolidated_bed"]["sha256"] = digest
            manifest_path.write_text(json.dumps(document) + "\n", encoding="utf-8")

    base = [20 + index * 3 for index in range(30)]
    control1 = base
    control2 = [max(10, value + ((index % 5) - 2) * 5) for index, value in enumerate(base)]
    treated1 = [value * 3 if index < 10 else max(10, value // 3) if index < 20 else value + 8 for index, value in enumerate(base)]
    treated2 = [max(10, value + ((index % 7) - 3) * 7) for index, value in enumerate(treated1)]
    counts = {
        "control_rep1": control1,
        "control_rep2": control2,
        "treated_rep1": treated1,
        "treated_rep2": treated2,
    }
    for record_id, values in counts.items():
        write_bam(root, record_id, sam_starts, values)


if __name__ == "__main__":
    main()
