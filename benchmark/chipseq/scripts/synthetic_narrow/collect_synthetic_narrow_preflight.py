#!/usr/bin/env python3
"""Verify the frozen synthetic-narrow runtime before FASTQ generation."""

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
CHIPS_COMMIT = "766c92cbb50783a537c897431b77e6bff8dba506"
CHIPS_SOURCE_SHA256 = "66577a898cb07986aab27124d748e146cb4c79a01694ce2e073ae45f2ff37ce0"
SCIENTIFIC_PATHS = ("main.nf", "nextflow.config", "nextflow_schema.json", "workflows", "subworkflows", "modules", "schemas", "pipelines")
PROTOCOL_FILES = (
    "benchmark/chipseq/protocol/design_freeze_report.md",
    "benchmark/chipseq/protocol/benchmark_protocol.md",
    "benchmark/chipseq/protocol/metrics.md",
    "benchmark/chipseq/protocol/interpretation_criteria.md",
    "benchmark/chipseq/protocol/chipseq_feature_matrix.tsv",
    "benchmark/chipseq/configs/narrow_design.json",
    "benchmark/chipseq/configs/macs3_parameters.json",
    "benchmark/chipseq/protocol/cost_estimate.md",
    "benchmark/chipseq/protocol/risks_and_limitations.md",
    "benchmark/chipseq/provenance/README.md",
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
    return value.splitlines()[0] if value.splitlines() else ""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--scratch", required=True, type=Path)
    parser.add_argument("--runtime", required=True, type=Path)
    parser.add_argument("--idr", required=True, type=Path)
    parser.add_argument("--chips", required=True, type=Path)
    parser.add_argument("--chips-source", required=True, type=Path)
    parser.add_argument("--java-home", required=True, type=Path)
    parser.add_argument("--r-bin", required=True, type=Path)
    parser.add_argument("--nextflow", required=True, type=Path)
    parser.add_argument("--git", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if "SLURM_JOB_ID" not in os.environ:
        raise RuntimeError("preflight must run in a Slurm allocation")

    repo, scratch = args.repo.resolve(), args.scratch.resolve()
    git = str(args.git.resolve())
    if not args.git.is_file():
        raise FileNotFoundError(f"Git executable not found: {args.git}")
    head = command([git, "-C", str(repo), "rev-parse", "HEAD"])
    target = command([git, "-C", str(repo), "rev-parse", SCIENTIFIC_TARGET])
    if target != SCIENTIFIC_TARGET:
        raise ValueError("scientific target cannot be resolved")
    if command([git, "-C", str(repo), "merge-base", "HEAD", PROTOCOL_COMMIT]) != PROTOCOL_COMMIT:
        raise ValueError("frozen protocol is not an ancestor of the benchmark branch")
    diff = subprocess.run(
        [git, "-C", str(repo), "diff", "--quiet", SCIENTIFIC_TARGET, "--", *SCIENTIFIC_PATHS], check=False
    )
    if diff.returncode:
        raise ValueError("scientific files differ from the target commit")

    design = json.loads((repo / "benchmark/chipseq/configs/narrow_design.json").read_text(encoding="utf-8"))
    macs = json.loads((repo / "benchmark/chipseq/configs/macs3_parameters.json").read_text(encoding="utf-8"))
    frozen = {
        "benchmark_id": design["benchmark_id"] == "chipseq-synthetic-narrow-v1",
        "chips": design["simulator"]["version"] == "v2.4" and design["simulator"]["commit"] == CHIPS_COMMIT,
        "seeds": design["simulator"]["seeds"] == {"replicate_1": 20260911, "replicate_2": 20260912, "input": 20260913},
        "truth": design["truth"]["peak_count"] == 1500 and design["truth"]["peak_width_bp"] == 400,
        "macs3": macs["macs3_version"] == "3.0.4" and macs["arms"]["synthetic_narrow"] == {
            "peak_type": "narrow", "format": "BAMPE", "effective_genome_size": 54000000
        },
        "idr": design["idr"] == {
            "version": "2.0.4.2", "rank": "signal_value", "threshold": 0.05,
            "replicate_mode": "biological", "input_policy": "require_premerged"
        },
    }
    if not all(frozen.values()):
        raise ValueError(f"frozen configuration mismatch: {frozen}")
    if sha256(args.chips_source) != CHIPS_SOURCE_SHA256:
        raise ValueError("ChIPs v2.4 source archive checksum mismatch")

    env = os.environ.copy()
    env["JAVA_HOME"] = str(args.java_home.resolve())
    env["NXF_VER"] = "25.10.7"
    env["PATH"] = os.pathsep.join((str(args.runtime.resolve() / "bin"), str(args.idr.resolve() / "bin"), str(args.java_home.resolve() / "bin"), env["PATH"]))
    nextflow_output = command([str(args.nextflow), "-version"], env)
    nextflow_version = next(
        (line.strip() for line in nextflow_output.splitlines() if line.strip().lower().startswith("version ")),
        "",
    )
    versions = {
        "java": first_line(command([str(args.java_home / "bin/java"), "-version"], env)),
        "nextflow": nextflow_version,
        "slurm": command(["srun", "--version"], env),
        "python": command([str(args.runtime / "bin/python"), "--version"], env),
        "r": first_line(command([str(args.r_bin), "--version"], env)),
        "chips": "v2.4 source-and-binary provenance verified",
        "bowtie2": first_line(command([str(args.runtime / "bin/bowtie2"), "--version"], env)),
        "samtools": first_line(command([str(args.runtime / "bin/samtools"), "--version"], env)),
        "macs3": command([str(args.runtime / "bin/macs3"), "--version"], env),
        "idr": first_line(command([str(args.idr / "bin/idr"), "--version"], env)),
        "fastqc": first_line(command([str(args.runtime / "bin/fastqc"), "--version"], env)),
        "multiqc": first_line(command([str(args.runtime / "bin/multiqc"), "--version"], env)),
    }
    expected = {
        "nextflow": nextflow_version.lower().startswith("version 25.10.7 "),
        "java": "21." in versions["java"],
        "bowtie2": "2.5.4" in versions["bowtie2"],
        "samtools": versions["samtools"] == "samtools 1.20",
        "macs3": versions["macs3"] == "macs3 3.0.4",
        "idr": versions["idr"] == "IDR 2.0.4.2",
        "fastqc": "v0.12.1" in versions["fastqc"],
        "multiqc": "1.35" in versions["multiqc"],
    }
    if not all(expected.values()):
        raise ValueError(f"runtime version mismatch: {expected}")

    usage = shutil.disk_usage(scratch)
    protocol = {name: sha256(repo / name) for name in PROTOCOL_FILES}
    result = {
        "schema_version": "1.0",
        "type": "synthetic_narrow_preflight",
        "status": "PASS",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "host": {"hostname": socket.getfqdn(), "platform": platform.platform(), "slurm_job_id": os.environ["SLURM_JOB_ID"]},
        "git": {"branch": command([git, "-C", str(repo), "branch", "--show-current"]), "head": head, "scientific_target": SCIENTIFIC_TARGET, "protocol_commit": PROTOCOL_COMMIT},
        "checks": {"scientific_target": True, "protocol": True, **frozen, **expected, "scratch": True, "disk": usage.free > 500_000_000_000},
        "versions": versions,
        "chips": {"commit": CHIPS_COMMIT, "source_sha256": CHIPS_SOURCE_SHA256, "binary_sha256": sha256(args.chips)},
        "protocol_sha256": protocol,
        "scratch": {"path": str(scratch), "total_bytes": usage.total, "free_bytes": usage.free},
    }
    if not all(result["checks"].values()):
        raise ValueError(f"preflight check failed: {result['checks']}")
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
