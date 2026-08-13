#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def rows_for(rows: list[dict[str, str]], process: str) -> list[dict[str, str]]:
    return [row for row in rows if process in row["name"]]


def statuses(rows: list[dict[str, str]], process: str) -> list[str]:
    return [row["status"].upper() for row in rows_for(rows, process)]


def assert_all(values: list[str], expected: str, label: str) -> None:
    if not values or any(value != expected for value in values):
        raise AssertionError(f"{label}: expected only {expected}, observed {values}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path)
    parser.add_argument(
        "scenario",
        choices=("identical", "fastq", "transcriptome", "parameters", "contrast", "qc", "module_script"),
    )
    args = parser.parse_args()
    with args.trace.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    if not rows:
        raise AssertionError("trace contains no processes")

    if args.scenario == "identical":
        non_cached = [(row["name"], row["status"]) for row in rows if row["status"].upper() != "CACHED"]
        if non_cached:
            raise AssertionError(f"identical resume reran processes: {non_cached}")
    elif args.scenario == "fastq":
        assert_all(statuses(rows, "SALMON_INDEX"), "CACHED", "Salmon index after FASTQ change")
        quant = statuses(rows, "SALMON_QUANT")
        if quant.count("COMPLETED") != 1 or quant.count("CACHED") != 3:
            raise AssertionError(f"FASTQ change must rerun one Salmon sample: {quant}")
        if "COMPLETED" not in statuses(rows, "TRIM_GALORE"):
            raise AssertionError("FASTQ change did not invalidate Trim Galore")
    elif args.scenario == "transcriptome":
        assert_all(statuses(rows, "SALMON_INDEX"), "COMPLETED", "Salmon index after transcriptome change")
        assert_all(statuses(rows, "SALMON_QUANT"), "COMPLETED", "Salmon quantification after transcriptome change")
        for process in ("TRIM_GALORE", "MERGE_FASTQ", "MULTIQC"):
            assert_all(statuses(rows, process), "CACHED", f"{process} after transcriptome change")
    elif args.scenario == "parameters":
        assert_all(statuses(rows, "SALMON_INDEX"), "CACHED", "Salmon index after quantification parameter change")
        assert_all(statuses(rows, "SALMON_QUANT"), "COMPLETED", "Salmon quantification after parameter change")
        for process in ("TRIM_GALORE", "MERGE_FASTQ", "MULTIQC"):
            assert_all(statuses(rows, process), "CACHED", f"{process} after parameter change")
    elif args.scenario == "contrast":
        assert_all(statuses(rows, "SALMON_IMPORT"), "CACHED", "Import after contrast change")
        assert_all(statuses(rows, "DESEQ2_MODEL"), "CACHED", "DESeq2 model after contrast change")
        for process in ("DE_PREFLIGHT", "DESEQ2_CONTRAST", "DE_AGGREGATE"):
            assert_all(statuses(rows, process), "COMPLETED", f"{process} after contrast change")
    elif args.scenario == "qc":
        assert_all(statuses(rows, "SALMON_INDEX"), "CACHED", "Salmon index after QC parameter change")
        assert_all(statuses(rows, "FASTQC_RAW"), "CACHED", "raw FastQC after QC parameter change")
        assert_all(statuses(rows, "RNASEQ_QC_PLAN"), "COMPLETED", "QC plan after QC parameter change")
        assert_all(statuses(rows, "TRIM_GALORE"), "COMPLETED", "Trim Galore after QC parameter change")
    else:
        assert_all(statuses(rows, "SALMON_INDEX"), "CACHED", "Salmon index after module script change")
        for process in ("RNASEQ_QC_PLAN", "TRIM_GALORE", "MULTIQC"):
            assert_all(statuses(rows, process), "CACHED", f"{process} after module script change")
        for process in ("SALMON_QUANT", "IMPORT_SOURCE", "SALMON_IMPORT", "DESEQ2_MODEL", "DESEQ2_CONTRAST", "DE_AGGREGATE"):
            assert_all(statuses(rows, process), "COMPLETED", f"{process} after module script change")

    print(f"[OK] Cache scenario {args.scenario}: {len(rows)} traced processes")


if __name__ == "__main__":
    main()
