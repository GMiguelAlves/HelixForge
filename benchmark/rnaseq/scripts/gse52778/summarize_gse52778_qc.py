#!/usr/bin/env python3
"""Build compact per-sample QC metrics from existing GSE52778 reports."""

from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
from pathlib import Path


def table(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def extract(report: Path, pattern: str, label: str) -> re.Match[str]:
    match = re.search(pattern, report.read_text(encoding="utf-8", errors="replace"), re.MULTILINE)
    if not match:
        raise ValueError(f"missing {label} in {report}")
    return match


def integer(text: str) -> int:
    return int(text.replace(",", ""))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample-table", required=True, type=Path)
    parser.add_argument("--trim-reports", required=True, type=Path)
    parser.add_argument("--multiqc-stats", required=True, type=Path)
    parser.add_argument("--quant-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--summary", required=True, type=Path)
    args = parser.parse_args()

    samples = table(args.sample_table)
    multiqc = {row["Sample"]: row for row in table(args.multiqc_stats)}
    records = []
    for sample in samples:
        sample_id = sample["sample_id"]
        mate_reports = {
            mate: args.trim_reports / f"{sample_id}_{mate}.fastq.gz_trimming_report.txt"
            for mate in ("R1", "R2")
        }
        raw = extract(
            mate_reports["R1"], r"^Total reads processed:\s+([0-9,]+)", "raw reads"
        )
        adapter = {}
        for mate, report in mate_reports.items():
            adapter[mate] = extract(
                report,
                r"^Reads with adapters:\s+([0-9,]+)\s+\(([0-9.]+)%\)",
                f"adapter reads {mate}",
            )
        removed = extract(
            mate_reports["R2"],
            r"^Number of sequence pairs removed.*:\s+([0-9,]+)\s+\(([0-9.]+)%\)",
            "removed pairs",
        )
        raw_pairs = integer(raw.group(1))
        removed_pairs = integer(removed.group(1))
        retained_pairs = raw_pairs - removed_pairs
        r1 = multiqc.get(f"{sample_id}_R1")
        r2 = multiqc.get(f"{sample_id}_R2")
        if r1 is None or r2 is None:
            raise ValueError(f"post-trim FastQC rows absent for {sample_id}")
        fastqc_pairs = int(float(r1["FastQC_mqc-generalstats-fastqc-total_sequences"]))
        if fastqc_pairs != retained_pairs or int(float(r2["FastQC_mqc-generalstats-fastqc-total_sequences"])) != retained_pairs:
            raise ValueError(f"Trim Galore/FastQC retained pair counts differ for {sample_id}")
        salmon = json.loads(
            (args.quant_root / sample_id / "aux_info/meta_info.json").read_text(encoding="utf-8")
        )
        if int(salmon["num_processed"]) != retained_pairs:
            raise ValueError(f"FastQC/Salmon processed pair counts differ for {sample_id}")
        records.append({
            "sample_id": sample_id,
            "condition": sample["condition"],
            "donor": sample["batch"],
            "raw_pairs": raw_pairs,
            "retained_pairs": retained_pairs,
            "removed_short_pairs": removed_pairs,
            "retention_percent": retained_pairs / raw_pairs * 100,
            "adapter_r1_percent": float(adapter["R1"].group(2)),
            "adapter_r2_percent": float(adapter["R2"].group(2)),
            "post_trim_r1_mean_length": float(r1["FastQC_mqc-generalstats-fastqc-avg_sequence_length"]),
            "post_trim_r2_mean_length": float(r2["FastQC_mqc-generalstats-fastqc-avg_sequence_length"]),
            "post_trim_r1_gc_percent": float(r1["FastQC_mqc-generalstats-fastqc-percent_gc"]),
            "post_trim_r2_gc_percent": float(r2["FastQC_mqc-generalstats-fastqc-percent_gc"]),
            "post_trim_r1_duplicate_percent": float(r1["FastQC_mqc-generalstats-fastqc-percent_duplicates"]),
            "post_trim_r2_duplicate_percent": float(r2["FastQC_mqc-generalstats-fastqc-percent_duplicates"]),
            "fastqc_failed_modules_percent_r1": float(r1["FastQC_mqc-generalstats-fastqc-percent_fails"]),
            "fastqc_failed_modules_percent_r2": float(r2["FastQC_mqc-generalstats-fastqc-percent_fails"]),
            "salmon_processed_fragments": int(salmon["num_processed"]),
            "salmon_mapped_fragments": int(salmon["num_mapped"]),
            "salmon_mapping_percent": float(salmon["percent_mapped"]),
        })

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(records)
    retention = [row["retention_percent"] for row in records]
    mapping = [row["salmon_mapping_percent"] for row in records]
    summary = {
        "schema_version": "1.0", "status": "complete", "dataset": "GSE52778",
        "samples": len(records), "raw_pairs": sum(row["raw_pairs"] for row in records),
        "retained_pairs": sum(row["retained_pairs"] for row in records),
        "retention_percent_min": min(retention), "retention_percent_median": statistics.median(retention),
        "retention_percent_max": max(retention),
        "salmon_mapping_percent_min": min(mapping),
        "salmon_mapping_percent_median": statistics.median(mapping),
        "salmon_mapping_percent_max": max(mapping),
        "sample_exclusions": [],
        "multiqc": "report_present",
        "multiqc_limitation": "KNOWN_REPORTING_LIMITATION:MULTIQC_SOFTWARE_TABLE_ABSENT",
        "outlier_policy": "descriptive only; no sample excluded automatically",
    }
    args.summary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "complete", "samples": len(records)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
