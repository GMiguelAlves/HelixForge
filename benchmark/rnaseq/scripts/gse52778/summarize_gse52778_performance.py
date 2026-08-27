#!/usr/bin/env python3
"""Summarize composite HelixForge and independent-reference Slurm performance."""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path


TASK = re.compile(
    r"TaskHandler\[jobId: (?P<job_id>[^;]+); id: (?P<task_id>[^;]+); "
    r"name: (?P<name>.*?); status: COMPLETED; exit: (?P<exit>[^;]+);.*?"
    r"workDir: (?P<workdir>\S+) started: (?P<started>[^;]+); exited: (?P<exited>[^;]+);"
)


def terminal_tasks(log: Path) -> list[dict[str, str]]:
    found = {}
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        match = TASK.search(line)
        if match:
            task = match.groupdict()
            found[(task["job_id"], task["task_id"], task["name"])] = task
    if not found:
        raise ValueError(f"no terminal tasks in {log}")
    return list(found.values())


def trace_values(workdir: Path) -> dict[str, str]:
    path = workdir / ".command.trace"
    if not path.is_file():
        return {}
    result = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[1:]:
        if "=" in line:
            key, value = line.split("=", 1)
            result[key] = value
    return result


def family(name: str) -> str:
    return name.split(" (", 1)[0].split(":")[-1]


def summarize_segment(label: str, log: Path) -> tuple[dict, list[dict[str, object]]]:
    tasks = terminal_tasks(log)
    groups = defaultdict(lambda: {
        "task_count": 0, "completed": 0, "failed": 0,
        "summed_realtime_seconds": 0.0, "summed_cpu_seconds": 0.0,
        "peak_rss_bytes": 0, "peak_vmem_bytes": 0,
        "read_bytes": 0, "write_bytes": 0, "missing_trace": 0,
    })
    starts, ends = [], []
    for task in tasks:
        current = trace_values(Path(task["workdir"]))
        realtime = float(current.get("realtime", 0)) / 1000
        cpu_fraction = float(current.get("%cpu", 0)) / 100
        started = float(task["started"]) / 1000 if task["started"].isdigit() else None
        if started is not None:
            starts.append(started)
            ends.append(started + realtime)
        for key in (family(task["name"]), "__all__"):
            item = groups[key]
            item["task_count"] += 1
            item["completed" if task["exit"] == "0" else "failed"] += 1
            item["summed_realtime_seconds"] += realtime
            item["summed_cpu_seconds"] += realtime * cpu_fraction
            item["peak_rss_bytes"] = max(item["peak_rss_bytes"], int(current.get("peak_rss", 0)) * 1024)
            item["peak_vmem_bytes"] = max(item["peak_vmem_bytes"], int(current.get("peak_vmem", 0)) * 1024)
            item["read_bytes"] += int(current.get("rchar", 0))
            item["write_bytes"] += int(current.get("wchar", 0))
            item["missing_trace"] += int(not bool(current))
    records = []
    for process, item in sorted(groups.items()):
        if process == "__all__":
            continue
        records.append({"phase": label, "process": process, **item})
    return {
        # Public summaries retain the segment identity without exposing the
        # institutional scratch path. The original log remains in the audit
        # archive on the cluster.
        "label": label, "log": log.name, "task_count": len(tasks),
        "wall_seconds": max(ends) - min(starts) if starts else None,
        "processes": dict(sorted(groups.items())),
    }, records


def parse_memory(value: str) -> int | None:
    value = value.strip()
    if not value:
        return None
    factors = {"K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}
    suffix = value[-1].upper()
    return int(float(value[:-1]) * factors[suffix]) if suffix in factors else int(value)


def slurm_jobs(job_ids: list[str], sacct_file: Path | None = None) -> list[dict[str, object]]:
    if sacct_file:
        output = sacct_file.read_text(encoding="utf-8")
    else:
        command = [
            "sacct", "-j", ",".join(job_ids), "--noheader", "--parsable2",
            "--format=JobIDRaw,State,ExitCode,ElapsedRaw,MaxRSS,AllocCPUS,NodeList",
        ]
        output = subprocess.run(
            command, check=True, text=True, capture_output=True
        ).stdout
    by_job: dict[str, dict[str, object]] = {}
    for line in output.splitlines():
        fields = line.split("|")
        if len(fields) < 7:
            continue
        parent = fields[0].split(".", 1)[0]
        if parent not in job_ids:
            continue
        memory = parse_memory(fields[4])
        if "." not in fields[0]:
            by_job[parent] = {
                "job_id": parent, "state": fields[1], "exit_code": fields[2],
                "elapsed_seconds": int(fields[3] or 0), "max_rss_bytes": memory,
                "allocated_cpus": int(fields[5] or 0),
                "node": "slurm_compute_node_redacted",
            }
        elif memory is not None:
            by_job.setdefault(parent, {"job_id": parent})["max_rss_bytes"] = max(
                int(by_job.get(parent, {}).get("max_rss_bytes") or 0), memory
            )
    return [by_job[job_id] for job_id in job_ids]


def disk_usage(path: Path) -> int:
    result = subprocess.run(["du", "-sb", str(path)], check=True, text=True, capture_output=True)
    return int(result.stdout.split()[0])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-root", required=True, type=Path)
    parser.add_argument("--independent-root", required=True, type=Path)
    parser.add_argument("--download-root", required=True, type=Path)
    parser.add_argument("--reference-root", required=True, type=Path)
    parser.add_argument("--external-job", action="append", required=True)
    parser.add_argument("--sacct-file", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--table-output", required=True, type=Path)
    args = parser.parse_args()

    logs = (
        ("HELIXFORGE_EXECUTION", args.case_root / "logs/nextflow.log"),
        ("HELIXFORGE_REPORT_RECOVERY", args.case_root / "report-hotfix-recovery/logs/nextflow.log"),
        ("HELIXFORGE_MANIFEST_RECOVERY", args.case_root / "terminal-manifest-recovery/logs/nextflow.log"),
    )
    segments, process_records = [], []
    for label, log in logs:
        segment, current = summarize_segment(label, log)
        segments.append(segment)
        process_records.extend(current)
    external = slurm_jobs(args.external_job, args.sacct_file)
    for job in external:
        process_records.append({
            "phase": "EXTERNAL_REFERENCE_EXECUTION", "process": f"slurm_job_{job['job_id']}",
            "task_count": 1, "completed": int(job["state"] == "COMPLETED"),
            "failed": int(job["state"] != "COMPLETED"),
            "summed_realtime_seconds": job["elapsed_seconds"],
            "summed_cpu_seconds": None, "peak_rss_bytes": job["max_rss_bytes"],
            "peak_vmem_bytes": None, "read_bytes": None, "write_bytes": None,
            "missing_trace": 0,
        })
    write_fields = list(process_records[0])
    args.table_output.parent.mkdir(parents=True, exist_ok=True)
    with args.table_output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=write_fields, delimiter="\t")
        writer.writeheader()
        writer.writerows(process_records)

    document = {
        "schema_version": "1.0", "status": "complete",
        "classification": "DESCRIPTIVE_CLUSTER_PERFORMANCE",
        "download_time": "reported_separately_in_download_provenance",
        "reference_preparation_time": "reported_separately_in_reference_provenance",
        "helixforge_segments": segments,
        "external_reference_jobs": external,
        "storage_bytes": {
            "download": disk_usage(args.download_root),
            "reference": disk_usage(args.reference_root),
            "helixforge_case": disk_usage(args.case_root),
            "helixforge_work": disk_usage(args.case_root / "work"),
            "helixforge_results": disk_usage(args.case_root / "results"),
            "independent_reference": disk_usage(args.independent_root),
        },
        "limitations": [
            "Shared-cluster measurements are descriptive and include scheduler/filesystem effects.",
            "The HelixForge result is a controlled composite recovery, not one uninterrupted run.",
            "External job 15986 completed all Salmon tasks but exited after the initial wrong-R probe; job 15988 completed tximport/DESeq2.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "complete", "process_rows": len(process_records)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
