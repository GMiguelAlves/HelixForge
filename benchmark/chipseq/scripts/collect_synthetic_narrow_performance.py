#!/usr/bin/env python3
"""Summarize trace, Slurm accounting and storage as descriptive performance."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
from collections import defaultdict
from pathlib import Path


SIZE_UNITS = {"B": 1, "KB": 1000, "MB": 1000**2, "GB": 1000**3, "TB": 1000**4}


def parse_duration(value: str) -> float:
    value = (value or "").strip()
    if not value or value == "-":
        return 0.0
    units = {"d": 86400, "h": 3600, "m": 60, "s": 1, "ms": 1e-3, "us": 1e-6, "µs": 1e-6, "ns": 1e-9}
    matches = re.findall(r"(\d+(?:\.\d+)?)\s*(ms|us|µs|ns|d|h|m|s)", value)
    return sum(float(number) * units[unit] for number, unit in matches) if matches else float(value)


def parse_size(value: str) -> int:
    fields = (value or "").strip().split()
    if not fields or fields[0] == "-":
        return 0
    return int(float(fields[0]) * SIZE_UNITS[fields[1].upper()]) if len(fields) > 1 else int(float(fields[0]))


def parse_memory(value: str) -> int | None:
    value = value.strip()
    if not value:
        return None
    factors = {"K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}
    suffix = value[-1].upper()
    return int(float(value[:-1]) * factors[suffix]) if suffix in factors else int(value)


def trace_summary(label: str, path: Path) -> tuple[dict, list[dict]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    if not rows:
        raise ValueError(f"empty trace: {path}")
    groups = defaultdict(lambda: {"task_count": 0, "completed": 0, "cached": 0, "failed": 0, "summed_duration_seconds": 0.0, "summed_realtime_seconds": 0.0, "summed_cpu_seconds": 0.0, "peak_rss_bytes": 0, "peak_vmem_bytes": 0, "read_bytes": 0, "write_bytes": 0})
    for row in rows:
        process = row.get("name", "").split(" (", 1)[0]
        duration, realtime = parse_duration(row.get("duration", "")), parse_duration(row.get("realtime", ""))
        cpu = float((row.get("%cpu") or "0").rstrip("%") or 0) / 100
        for key in (process, "__all__"):
            item = groups[key]
            item["task_count"] += 1
            status = row.get("status", "").upper()
            item["cached" if status == "CACHED" else "completed" if status == "COMPLETED" else "failed"] += 1
            item["summed_duration_seconds"] += duration
            item["summed_realtime_seconds"] += realtime
            item["summed_cpu_seconds"] += realtime * cpu
            item["peak_rss_bytes"] = max(item["peak_rss_bytes"], parse_size(row.get("peak_rss", "")))
            item["peak_vmem_bytes"] = max(item["peak_vmem_bytes"], parse_size(row.get("peak_vmem", "")))
            item["read_bytes"] += parse_size(row.get("rchar", ""))
            item["write_bytes"] += parse_size(row.get("wchar", ""))
    records = [{"phase": label, "process": process, **values} for process, values in sorted(groups.items()) if process != "__all__"]
    return {"label": label, "path": path.name, "tasks": len(rows), "summary": groups["__all__"]}, records


def slurm_summary(path: Path) -> list[dict]:
    jobs = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split("|")
        if len(fields) < 8 or not fields[0]:
            continue
        parent = fields[0].split(".", 1)[0]
        memory = parse_memory(fields[5])
        job = jobs.setdefault(parent, {"job_id": parent, "job_name": fields[1], "state": fields[2], "exit_code": fields[3], "elapsed_seconds": int(fields[4] or 0), "max_rss_bytes": None, "allocated_cpus": int(fields[6] or 0), "node": fields[7]})
        if memory is not None:
            job["max_rss_bytes"] = max(job["max_rss_bytes"] or 0, memory)
    return [jobs[key] for key in sorted(jobs, key=lambda value: int(value) if value.isdigit() else value)]


def directory_size(path: Path) -> int:
    completed = subprocess.run(["du", "-sb", str(path)], capture_output=True, text=True, check=True)
    return int(completed.stdout.split()[0])


def assignment(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("expected LABEL=PATH")
    label, path = value.split("=", 1)
    return label, Path(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace", action="append", required=True, type=assignment)
    parser.add_argument("--sacct", required=True, type=Path)
    parser.add_argument("--storage", action="append", required=True, type=assignment)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-tsv", required=True, type=Path)
    args = parser.parse_args()
    if "SLURM_JOB_ID" not in os.environ:
        raise RuntimeError("performance collection must run under Slurm")
    traces, process_rows = [], []
    for label, path in args.trace:
        summary, rows = trace_summary(label, path)
        traces.append(summary)
        process_rows.extend(rows)
    with args.output_tsv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(process_rows[0]), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(process_rows)
    document = {
        "schema_version": "1.0", "type": "synthetic_narrow_performance", "classification": "DESCRIPTIVE_CLUSTER_PERFORMANCE",
        "status": "complete", "collector_slurm_job_id": os.environ["SLURM_JOB_ID"], "traces": traces,
        "slurm_jobs": slurm_summary(args.sacct),
        "storage_bytes": {label: directory_size(path) for label, path in args.storage},
        "limitations": ["Shared-cluster measurements include scheduler and NFS effects and are not release gates."],
    }
    args.output_json.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
