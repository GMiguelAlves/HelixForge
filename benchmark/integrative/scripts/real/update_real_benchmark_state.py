#!/usr/bin/env python3
"""Create or atomically update the persistent state of the real benchmark."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile
from typing import Any


PHASE_RANK = {
    "METADATA_PREFLIGHT_PREPARED": 10,
    "METADATA_PREFLIGHT_SUBMITTED": 20,
    "METADATA_PREFLIGHT_RUNNING": 30,
    "METADATA_PREFLIGHT_FAILED": 40,
    "METADATA_PREFLIGHT_COMPLETE": 50,
    "FASTQ_DOWNLOAD_PREPARED": 60,
    "FASTQ_DOWNLOAD_SUBMITTED": 70,
    "FASTQ_DOWNLOAD_FAILED": 80,
    "FASTQ_DOWNLOAD_COMPLETE": 90,
    "REFERENCE_PREPARED": 100,
    "REFERENCE_SUBMITTED": 110,
    "REFERENCE_FAILED": 120,
    "REFERENCE_COMPLETE": 130,
    "UPSTREAM_INPUTS_PREPARED": 140,
    "UPSTREAM_INPUTS_SUBMITTED": 150,
    "UPSTREAM_INPUTS_FAILED": 160,
    "UPSTREAM_INPUTS_COMPLETE": 170,
    "RNASEQ_SUBMITTED": 180,
    "RNASEQ_FAILED": 190,
    "RNASEQ_COMPLETE": 200,
    "CHIPSEQ_H3K27ME3_SUBMITTED": 210,
    "CHIPSEQ_H3K27ME3_FAILED": 220,
    "CHIPSEQ_H3K27ME3_COMPLETE": 230,
    "CHIPSEQ_H3K27AC_SUBMITTED": 240,
    "CHIPSEQ_H3K27AC_FAILED": 250,
    "CHIPSEQ_H3K27AC_COMPLETE": 260,
}


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "schema_version": "1.0",
            "benchmark": "GSE133183 real biological integration",
            "scientific_target_commit": "dc0218ce902302da476910595bb133c82fee927c",
            "scientific_stage_order": ["10B", "10C", "10D", "10E", "10F"],
            "operational_stage_order": ["10B", "10C", "10E", "10D"],
            "jobs": [],
            "workdirs": [],
            "expected_outputs": [],
        }
    return json.loads(path.read_text(encoding="utf-8"))


def unique_append(values: list[Any], value: Any) -> None:
    if value not in values:
        values.append(value)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--phase", required=True, choices=sorted(PHASE_RANK))
    parser.add_argument("--status", required=True)
    parser.add_argument("--session-uuid")
    parser.add_argument("--job-id")
    parser.add_argument("--job-kind", default="metadata_preflight")
    parser.add_argument("--workdir")
    parser.add_argument("--repo-commit")
    parser.add_argument("--expected-output", action="append", default=[])
    args = parser.parse_args()

    state = load_state(args.state)
    current_phase = state.get("phase", "METADATA_PREFLIGHT_PREPARED")
    if PHASE_RANK[args.phase] >= PHASE_RANK.get(current_phase, 0):
        state["phase"] = args.phase
        state["status"] = args.status
        state["last_known_state"] = args.status
    if args.session_uuid:
        state["session_uuid"] = args.session_uuid
    if args.repo_commit:
        state["execution_repository_commit"] = args.repo_commit
    if args.workdir:
        unique_append(state.setdefault("workdirs", []), args.workdir)
    for output in args.expected_output:
        unique_append(state.setdefault("expected_outputs", []), output)
    if args.job_id:
        jobs = state.setdefault("jobs", [])
        existing = next((job for job in jobs if str(job.get("job_id")) == args.job_id), None)
        if existing is None:
            existing = {"job_id": args.job_id, "kind": args.job_kind}
            jobs.append(existing)
        existing["last_reported_status"] = args.status
        existing["phase"] = args.phase

    state["updated_utc"] = os.environ.get("HF_STATE_TIME_UTC")
    args.state.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=args.state.parent, delete=False
    ) as handle:
        json.dump(state, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(args.state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
