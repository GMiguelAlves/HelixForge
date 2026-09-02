#!/usr/bin/env python3
"""Consolidate the per-sample checksum and integrity evidence from acquisition."""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
import re
from typing import Any


def read_rows(path: Path, delimiter: str = "\t") -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


def write_tsv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scratch-root", required=True, type=Path)
    parser.add_argument("--download-manifest", required=True, type=Path)
    parser.add_argument("--array-job-id", required=True)
    parser.add_argument("--sacct", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    if not os.environ.get("SLURM_JOB_ID"):
        raise SystemExit("download consolidation must execute inside a Slurm job")
    if args.output_dir.exists():
        raise FileExistsError(args.output_dir)
    args.output_dir.mkdir(parents=True)

    expected_rows = read_rows(args.download_manifest)
    if len(expected_rows) != 32:
        raise ValueError("expected exactly 32 frozen FASTQ records")
    expected = {(row["geo_sample"], row["run_accession"], row["mate"]): row for row in expected_rows}
    observed: dict[tuple[str, str, str], dict[str, str]] = {}
    executions: list[dict[str, str]] = []
    for gsm in sorted({row["geo_sample"] for row in expected_rows}):
        file_rows = read_rows(args.scratch_root / "download_manifests" / f"{gsm}.files.tsv")
        execution_rows = read_rows(args.scratch_root / "download_manifests" / f"{gsm}.execution.tsv")
        if len(file_rows) != 2 or len(execution_rows) != 1 or execution_rows[0]["status"] != "COMPLETE":
            raise ValueError(f"incomplete acquisition manifest for {gsm}")
        executions.extend(execution_rows)
        for row in file_rows:
            key = (row["geo_sample"], row["run_accession"], row["mate"])
            if key in observed:
                raise ValueError(f"duplicate observed FASTQ record: {key}")
            observed[key] = row
    if set(observed) != set(expected):
        raise ValueError("observed FASTQ key set differs from the frozen download manifest")

    inventory: list[dict[str, Any]] = []
    for key in sorted(expected):
        frozen, record = expected[key], observed[key]
        path = Path(record["path"])
        if not path.is_file():
            raise FileNotFoundError(path)
        if int(record["bytes"]) != int(frozen["bytes"]) or path.stat().st_size != int(frozen["bytes"]):
            raise ValueError(f"size mismatch for {key}")
        if record["md5"] != frozen["md5"]:
            raise ValueError(f"MD5 manifest mismatch for {key}")
        inventory.append({
            "geo_sample": key[0],
            "run_accession": key[1],
            "mate": key[2],
            "path": str(path),
            "bytes": frozen["bytes"],
            "official_md5": frozen["md5"],
            "verification": "MD5_AND_GZIP_VALIDATED_IN_COMPLETED_ARRAY_TASK",
        })

    task_rows: list[dict[str, str]] = []
    batch_rss: dict[str, str] = {}
    with args.sacct.open(encoding="utf-8") as handle:
        for raw in handle:
            fields = raw.rstrip("\n").split("|")
            if len(fields) < 5:
                continue
            batch_match = re.fullmatch(rf"({re.escape(args.array_job_id)}_\d+)\.batch", fields[0])
            if batch_match:
                batch_rss[batch_match.group(1)] = fields[4]
                continue
            if not re.fullmatch(rf"{re.escape(args.array_job_id)}_\d+", fields[0]):
                continue
            task_rows.append({
                "job_id": fields[0], "state": fields[1], "exit_code": fields[2],
                "elapsed": fields[3], "max_rss": "",
            })
    if len(task_rows) != 16 or any(row["state"] != "COMPLETED" or row["exit_code"] != "0:0" for row in task_rows):
        raise ValueError("Slurm accounting does not show 16 successful array tasks")
    for row in task_rows:
        row["max_rss"] = batch_rss.get(row["job_id"], "")
    if any(not row["max_rss"] for row in task_rows):
        raise ValueError("Slurm accounting lacks MaxRSS for one or more array tasks")

    success_lines = 0
    transfer_errors = 0
    for task in range(1, 17):
        stdout = (args.scratch_root / "logs" / f"download-{args.array_job_id}_{task}.out").read_text(encoding="utf-8", errors="replace")
        stderr = (args.scratch_root / "logs" / f"download-{args.array_job_id}_{task}.err").read_text(encoding="utf-8", errors="replace")
        success_lines += sum(line.endswith(("OK", "SUCESSO")) for line in stdout.splitlines())
        transfer_errors += len(re.findall(r"(?:curl:|failed|error)", stderr, flags=re.IGNORECASE))
    if success_lines != 32 or transfer_errors:
        raise ValueError(f"unexpected acquisition logs: checksum_success={success_lines}, errors={transfer_errors}")

    write_tsv(args.output_dir / "fastq_inventory.tsv", inventory)
    write_tsv(args.output_dir / "download_performance.tsv", task_rows)
    write_tsv(args.output_dir / "sample_execution.tsv", executions)
    summary = {
        "schema_version": "1.0",
        "status": "FASTQ_DOWNLOAD_VALIDATED",
        "array_job_id": args.array_job_id,
        "samples": 16,
        "runs": 16,
        "fastq_files": 32,
        "total_bytes": sum(int(row["bytes"]) for row in expected_rows),
        "official_md5_successes": success_lines,
        "gzip_integrity_checks": 32,
        "slurm_tasks_completed": 16,
        "transfer_error_markers": transfer_errors,
        "content_verification": "Each acquisition task validated official MD5 and gzip integrity before atomic .part rename; consolidation revalidated manifests, sizes, Slurm completion and logs without a redundant 230 GiB content pass.",
        "scientific_results_inspected": False,
    }
    (args.output_dir / "download_validation.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
