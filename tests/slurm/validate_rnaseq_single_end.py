#!/usr/bin/env python3
"""Validate a real-tool, reduced single-end RNA-seq Slurm case.

The generic RNA-seq scientific validator runs separately. This file checks
single-end layout, the technical-run merge, provider commands, and task status.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import shlex
from collections import Counter, defaultdict
from pathlib import Path


def table(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter="\t" if path.suffix == ".tsv" else ","))


def require_file(path: Path) -> None:
    if not path.is_file() or path.stat().st_size == 0:
        raise AssertionError(f"missing or empty file: {path}")


def process_name(trace_name: str) -> str:
    return trace_name.split(" (", 1)[0].rsplit(":", 1)[-1]


def process_rows(rows: list[dict[str, str]], name: str) -> list[dict[str, str]]:
    return [row for row in rows if process_name(row["name"]) == name]


def assert_process_count(rows: list[dict[str, str]], name: str, expected: int) -> None:
    actual = len(process_rows(rows, name))
    if actual != expected:
        raise AssertionError(f"{name}: expected {expected} tasks, observed {actual}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("case_root", type=Path)
    parser.add_argument("--scenario", choices=("baseline", "resume"), required=True)
    parser.add_argument("--technical-split", action="store_true")
    args = parser.parse_args()
    root = args.case_root
    n_runs = 5 if args.technical_split else 4

    metadata = table(root / "metadata.csv")
    if len(metadata) != n_runs or len({row["sample_id"] for row in metadata}) != 4:
        raise AssertionError("fixture must contain four biological samples and the expected runs")
    by_sample: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in metadata:
        if row["library_layout"] != "single":
            raise AssertionError(f"not single-end: {row}")
        if row.get("fastq_2", ""):
            raise AssertionError(f"single-end metadata contains R2: {row}")
        if (int(row["fragment_length_mean"]), int(row["fragment_length_sd"])) != (200, 80):
            raise AssertionError(f"fragment prior changed: {row}")
        by_sample[row["sample_id"]].append(row)
    if args.technical_split and len(by_sample["control_1"]) != 2:
        raise AssertionError("the technical-run fixture did not split control_1")
    if not args.technical_split and any(len(rows) != 1 for rows in by_sample.values()):
        raise AssertionError("baseline fixture unexpectedly has multiple technical runs")

    raw_root = root / "inputs/SYNTHETIC"
    if list((raw_root / "fastq_ftp").glob("*_R2.fastq.gz")):
        raise AssertionError("single-end fixture unexpectedly contains raw R2 files")
    for phase, expected in (("fastqc_raw", n_runs),
                            ("fastqc_trimmed_runs", n_runs),
                            ("fastqc_merged", 4)):
        found = list((raw_root / phase).glob("*_fastqc.zip"))
        if len(found) != expected:
            raise AssertionError(f"{phase}: expected {expected} FastQC archives, found {len(found)}")
        for path in found:
            require_file(path)
    require_file(raw_root / "multiqc_030/SYNTHETIC_multiqc_030.html")
    if not (raw_root / "multiqc_030/SYNTHETIC_multiqc_030_data").is_dir():
        raise AssertionError("MultiQC data directory is missing")

    expected_counts = table(root / "expected_counts.tsv")
    for sample, runs in by_sample.items():
        ordered = sorted(runs, key=lambda row: row["run_accession"])
        pieces = []
        for row in ordered:
            raw = raw_root / "fastq_ftp" / f"{sample}_{row['run_accession']}_R1.fastq.gz"
            trimmed = raw_root / "trimmed_runs" / f"{sample}_{row['run_accession']}_R1_trimmed.fastq.gz"
            require_file(raw)
            require_file(trimmed)
            pieces.append(trimmed.read_bytes())
        merged = raw_root / "trimmed_merged" / f"{sample}_R1_trimmed.fastq.gz"
        require_file(merged)
        if merged.read_bytes() != b"".join(pieces):
            raise AssertionError(f"{sample}: merged FASTQ is not the ordered concatenation of trimmed runs")
        with gzip.open(merged, "rt", encoding="ascii") as handle:
            lines = sum(1 for _ in handle)
        expected_reads = sum(int(row[sample]) for row in expected_counts)
        if lines % 4 or lines // 4 != expected_reads:
            raise AssertionError(f"{sample}: expected {expected_reads} reads, observed {lines // 4}")
    if list((raw_root / "trimmed_runs").glob("*_R2_trimmed.fastq.gz")) or list(
        (raw_root / "trimmed_merged").glob("*_R2_trimmed.fastq.gz")
    ):
        raise AssertionError("single-end QC unexpectedly emitted R2")

    command_root = root / "results/pipeline_info/native_quantification/salmon_quant"
    commands = list(command_root.glob("*.quantification_logs/command.txt"))
    if len(commands) != 4:
        raise AssertionError(f"expected four Salmon command logs, found {len(commands)}")
    for path in commands:
        tokens = shlex.split(path.read_text(encoding="utf-8"))
        if "-r" not in tokens or "-1" in tokens or "-2" in tokens:
            raise AssertionError(f"Salmon did not use single-end input: {path}")
        for option, expected in (("--fldMean", "200"), ("--fldSD", "80")):
            if option not in tokens or tokens[tokens.index(option) + 1] != expected:
                raise AssertionError(f"Salmon {option} differs from the fixture: {path}")

    manifest_path = root / "results/rnaseq/rnaseq_run_manifest.json"
    require_file(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    samples = manifest.get("samples", [])
    if len(samples) != 4 or any(sample.get("library_layout") != "single" for sample in samples):
        raise AssertionError("terminal manifest lost single-end sample layout")
    if any((sample.get("fragment_length_mean"), sample.get("fragment_length_sd")) != (200, 80)
           for sample in samples):
        raise AssertionError("terminal manifest lost the fragment prior")

    trace_path = root / "traces" / f"{args.scenario}.tsv"
    traces = table(trace_path)
    if not traces:
        raise AssertionError("trace is empty")
    for name, count in (("FASTQC_RAW", n_runs), ("FASTQC_TRIMMED", n_runs),
                        ("FASTQC_MERGED", 4), ("TRIM_GALORE_SINGLE", n_runs),
                        ("MERGE_FASTQ_SINGLE", 4), ("MULTIQC", 1),
                        ("SALMON_INDEX", 1), ("SALMON_QUANT", 4)):
        assert_process_count(traces, name, count)
    for forbidden in ("TRIM_GALORE", "MERGE_FASTQ", "STAR_INDEX", "STAR_ALIGN"):
        assert_process_count(traces, forbidden, 0)
    statuses = Counter(row["status"].upper() for row in traces)
    if args.scenario == "resume":
        repeated = [(row["name"], row["status"]) for row in traces
                    if row["status"].upper() != "CACHED"
                    and not process_name(row["name"]).endswith("RUN_MANIFEST")]
        if repeated:
            raise AssertionError(f"identical resume repeated scientific tasks: {repeated}")
    elif any(row["status"].upper() != "COMPLETED" for row in traces):
        raise AssertionError(f"fresh baseline contains non-completed tasks: {statuses}")

    report = {
        "status": "pass", "scenario": args.scenario, "technical_split": args.technical_split,
        "biological_samples": len(by_sample), "technical_runs": n_runs,
        "fastqc_archives": {"raw": n_runs, "trimmed": n_runs, "merged": 4},
        "salmon_commands": len(commands), "trace_statuses": dict(statuses),
    }
    output = root / f"validation-single-end-{args.scenario}.json"
    output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(f"[OK] single-end {args.scenario}: {n_runs} runs, 4 samples, {len(traces)} tasks")


if __name__ == "__main__":
    main()
