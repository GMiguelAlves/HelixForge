#!/usr/bin/env python3
"""Validate the frozen Real Broad contract and runtime inside Slurm."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path


SCIENTIFIC_TARGET = "0829c7c154dc634ffd4e13672b95ad4fbdc5957f"
PROTOCOL_COMMIT = "bb8db940ee137fee67fe5f13530521326c96dfc0"
PROTOCOL_FILES = (
    "benchmark/chipseq/configs/real_broad_execution.json",
    "benchmark/chipseq/configs/macs3_parameters.json",
    "benchmark/chipseq/datasets/real_broad_samples.tsv",
    "benchmark/chipseq/datasets/real_broad_biological_expectations.tsv",
    "benchmark/chipseq/datasets/reference_sources.tsv",
    "benchmark/chipseq/protocol/design_freeze_report.md",
    "benchmark/chipseq/protocol/benchmark_protocol.md",
    "benchmark/chipseq/protocol/metrics.md",
    "benchmark/chipseq/protocol/interpretation_criteria.md",
    "benchmark/chipseq/protocol/risks_and_limitations.md",
    "benchmark/chipseq/provenance/real_broad_repository_identity.json",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def command(argv: list[str], env: dict[str, str] | None = None) -> str:
    completed = subprocess.run(argv, capture_output=True, text=True, check=False, env=env)
    if completed.returncode:
        raise RuntimeError(f"command failed ({completed.returncode}): {' '.join(argv)}\n{completed.stderr.strip()}")
    return (completed.stdout or completed.stderr).strip()


def first_line(value: str) -> str:
    lines = value.splitlines()
    return lines[0] if lines else ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--scratch", required=True, type=Path)
    parser.add_argument("--home", required=True, type=Path)
    parser.add_argument("--runtime", required=True, type=Path)
    parser.add_argument("--r-bin", required=True, type=Path)
    parser.add_argument("--java-home", required=True, type=Path)
    parser.add_argument("--nextflow", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if "SLURM_JOB_ID" not in os.environ:
        raise RuntimeError("preflight must run in a Slurm allocation")

    repo = args.repo.resolve()
    config = json.loads((repo / "benchmark/chipseq/configs/real_broad_execution.json").read_text(encoding="utf-8"))
    identity = json.loads((repo / "benchmark/chipseq/provenance/real_broad_repository_identity.json").read_text(encoding="utf-8"))
    macs = json.loads((repo / "benchmark/chipseq/configs/macs3_parameters.json").read_text(encoding="utf-8"))
    frozen = {
        "benchmark_id": config["benchmark_id"] == "chipseq-real-broad-k562-h3k27me3-v1",
        "scientific_target": config["scientific_target"] == SCIENTIFIC_TARGET,
        "protocol_commit": config["protocol_commit"] == PROTOCOL_COMMIT,
        "repository_identity": identity["scientific_target"] == SCIENTIFIC_TARGET
        and identity["scientific_diff_from_target"] is False,
        "dataset": config["dataset"]["replicate_files"] == ["ENCFF000BXP", "ENCFF000BXN"]
        and config["dataset"]["control_file"] == "ENCFF000BWK",
        "reference": config["reference"]["assembly"] == "GRCh38.p14"
        and config["reference"]["blacklist_file"] == "ENCFF356LFX",
        "run_mode": config["processing"]["run_mode"] == "consensus"
        and config["processing"]["minimum_replicate_support"] == 2,
        "macs3": macs["macs3_version"] == "3.0.4"
        and macs["arms"]["real_broad"] == {
            "peak_type": "broad",
            "format": "BAM",
            "effective_genome_size": 2913022398,
            "broad_cutoff": "MACS3 default (0.1)",
        },
        "broad_idr_disabled": config["processing"]["idr"]["enabled"] is False,
        "external_reference": config["external_references"]["encode_replicated_broad_peaks"] == "ENCFF049HUP",
    }

    env = os.environ.copy()
    env["JAVA_HOME"] = str(args.java_home.resolve())
    env["NXF_VER"] = "25.10.7"
    env["PATH"] = os.pathsep.join((str(args.java_home / "bin"), str(args.runtime / "bin"), "/usr/bin", "/bin"))
    nextflow_output = command([str(args.nextflow), "-version"], env)
    nextflow_version = next((line.strip() for line in nextflow_output.splitlines() if line.strip().lower().startswith("version ")), "")
    versions = {
        "os": platform.platform(),
        "java": first_line(command([str(args.java_home / "bin/java"), "-version"], env)),
        "nextflow": nextflow_version,
        "slurm": command(["scontrol", "--version"], env),
        "python": command([str(args.runtime / "bin/python"), "--version"], env),
        "r": first_line(command([str(args.r_bin.resolve()), "--version"], env)),
        "bowtie2": first_line(command([str(args.runtime / "bin/bowtie2"), "--version"], env)),
        "samtools": first_line(command([str(args.runtime / "bin/samtools"), "--version"], env)),
        "macs3": command([str(args.runtime / "bin/macs3"), "--version"], env),
        "fastqc": first_line(command([str(args.runtime / "bin/fastqc"), "--version"], env)),
        "multiqc": first_line(command([str(args.runtime / "bin/multiqc"), "--version"], env)),
        "bedtools": command([str(args.runtime / "bin/bedtools"), "--version"], env),
    }
    expected = {
        "nextflow": nextflow_version.lower().startswith("version 25.10.7 "),
        "java": "21." in versions["java"],
        "bowtie2": "2.5.4" in versions["bowtie2"],
        "samtools": versions["samtools"] == "samtools 1.20",
        "macs3": versions["macs3"] == "macs3 3.0.4",
        "fastqc": "v0.12.1" in versions["fastqc"],
        "multiqc": "1.35" in versions["multiqc"],
        "bedtools": "v2.31.1" in versions["bedtools"],
        "python": bool(versions["python"]),
        "r": bool(versions["r"]),
    }

    scratch_usage = shutil.disk_usage(args.scratch)
    home_usage = shutil.disk_usage(args.home)
    checks = {
        **frozen,
        **expected,
        "scratch_free": scratch_usage.free > 100_000_000_000,
        "home_free": home_usage.free > 10_000_000_000,
    }
    result = {
        "schema_version": "1.0",
        "type": "real_broad_preflight",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "host": {"hostname": socket.getfqdn(), "slurm_job_id": os.environ["SLURM_JOB_ID"]},
        "git": identity,
        "checks": checks,
        "versions": versions,
        "protocol_sha256": {name: sha256(repo / name) for name in PROTOCOL_FILES},
        "storage": {
            "scratch": {"path": str(args.scratch.resolve()), "total_bytes": scratch_usage.total, "free_bytes": scratch_usage.free},
            "home": {"path": str(args.home.resolve()), "total_bytes": home_usage.total, "free_bytes": home_usage.free},
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
