#!/usr/bin/env python3
"""Summarize Nextflow trace and storage evidence for benchmark runs."""

from __future__ import annotations

import argparse
import csv
import json
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path


SIZE_UNITS = {
    "B": 1,
    "KB": 1000,
    "MB": 1000**2,
    "GB": 1000**3,
    "TB": 1000**4,
}


def parse_duration(value: str) -> float:
    value = (value or "").strip()
    if not value or value == "-":
        return 0.0
    total = 0.0
    number = ""
    units = {"d": 86400, "h": 3600, "m": 60, "s": 1}
    for char in value:
        if char.isdigit() or char == ".":
            number += char
        elif char in units and number:
            total += float(number) * units[char]
            number = ""
    if number:
        total += float(number)
    return total


def parse_size(value: str) -> int:
    fields = (value or "").strip().split()
    if not fields or fields[0] == "-":
        return 0
    if len(fields) == 1:
        return int(float(fields[0]))
    return int(float(fields[0]) * SIZE_UNITS[fields[1].upper()])


def directory_size(path: Path) -> int:
    total = 0
    if not path.exists():
        return total
    for root, _, files in os.walk(path):
        for name in files:
            file_path = Path(root, name)
            try:
                total += file_path.stat().st_size
            except FileNotFoundError:
                pass
    return total


def process_family(name: str) -> str:
    return name.split(" (", 1)[0]


def summarize_case(case_root: Path) -> dict:
    identity_path = case_root / "execution_identity.json"
    trace_path = case_root / "results/pipeline_info/execution_trace.tsv"
    identity = json.loads(identity_path.read_text(encoding="utf-8"))
    rows = list(csv.DictReader(trace_path.open(encoding="utf-8"), delimiter="\t"))
    started = datetime.fromisoformat(identity["started_utc"].replace("Z", "+00:00"))
    ended = datetime.fromisoformat(identity["ended_utc"].replace("Z", "+00:00"))

    families: dict[str, dict] = defaultdict(
        lambda: {
            "task_count": 0,
            "completed": 0,
            "cached": 0,
            "failed": 0,
            "summed_duration_seconds": 0.0,
            "summed_realtime_seconds": 0.0,
            "summed_scheduler_wait_seconds": 0.0,
            "summed_cpu_seconds": 0.0,
            "peak_rss_bytes": 0,
            "peak_vmem_bytes": 0,
            "read_bytes": 0,
            "write_bytes": 0,
        }
    )
    all_tasks = families["__all__"]
    for row in rows:
        duration = parse_duration(row.get("duration", ""))
        realtime = parse_duration(row.get("realtime", ""))
        cpu_fraction = float((row.get("%cpu") or "0").rstrip("%") or 0) / 100.0
        rss = parse_size(row.get("peak_rss", ""))
        vmem = parse_size(row.get("peak_vmem", ""))
        read_bytes = parse_size(row.get("rchar", ""))
        write_bytes = parse_size(row.get("wchar", ""))
        for summary in (families[process_family(row["name"])], all_tasks):
            summary["task_count"] += 1
            status = row.get("status", "").upper()
            if status == "COMPLETED":
                summary["completed"] += 1
            elif status == "CACHED":
                summary["cached"] += 1
            else:
                summary["failed"] += 1
            summary["summed_duration_seconds"] += duration
            summary["summed_realtime_seconds"] += realtime
            summary["summed_scheduler_wait_seconds"] += max(duration - realtime, 0.0)
            summary["summed_cpu_seconds"] += realtime * cpu_fraction
            summary["peak_rss_bytes"] = max(summary["peak_rss_bytes"], rss)
            summary["peak_vmem_bytes"] = max(summary["peak_vmem_bytes"], vmem)
            summary["read_bytes"] += read_bytes
            summary["write_bytes"] += write_bytes

    for summary in families.values():
        for field, value in list(summary.items()):
            if isinstance(value, float):
                summary[field] = round(value, 6)

    return {
        "case": case_root.name,
        "identity": identity,
        "workflow_wall_seconds": (ended - started).total_seconds(),
        "trace": {
            "path": str(trace_path),
            "task_count": len(rows),
            "processes": dict(sorted(families.items())),
        },
        "storage_bytes": {
            "case_total": directory_size(case_root),
            "work": directory_size(case_root / "work"),
            "results": directory_size(case_root / "results"),
            "nextflow_home": directory_size(case_root / "nxf-home"),
            "nextflow_cache": directory_size(case_root / "nxf-cache"),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", action="append", required=True, type=Path)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--runtime-cache", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    cases = [summarize_case(case) for case in args.case]
    report = {
        "status": "pass" if all(c["trace"]["processes"]["__all__"]["failed"] == 0 for c in cases) else "fail",
        "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
        "node": os.uname().nodename,
        "cases": cases,
        "shared_storage_bytes": {
            "reference": directory_size(args.reference) if args.reference else None,
            "runtime_cache": directory_size(args.runtime_cache) if args.runtime_cache else None,
        },
    }
    if not report["slurm_job_id"]:
        raise SystemExit("performance aggregation must execute inside a Slurm job")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "cases": len(cases)}))


if __name__ == "__main__":
    main()
