#!/usr/bin/env python3
"""Validate the frozen runtime and repository before real-narrow downloads."""

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
SCIENTIFIC_PATHS = (
    "main.nf", "nextflow.config", "nextflow_schema.json", "workflows",
    "subworkflows", "modules", "schemas", "pipelines",
)
PROTOCOL_FILES = (
    "benchmark/chipseq/protocol/design_freeze_report.md",
    "benchmark/chipseq/protocol/benchmark_protocol.md",
    "benchmark/chipseq/protocol/metrics.md",
    "benchmark/chipseq/protocol/interpretation_criteria.md",
    "benchmark/chipseq/protocol/chipseq_feature_matrix.tsv",
    "benchmark/chipseq/configs/macs3_parameters.json",
    "benchmark/chipseq/configs/real_narrow_execution.json",
    "benchmark/chipseq/datasets/real_narrow_samples.tsv",
    "benchmark/chipseq/datasets/real_narrow_biological_expectations.tsv",
    "benchmark/chipseq/datasets/reference_sources.tsv",
    "benchmark/chipseq/protocol/cost_estimate.md",
    "benchmark/chipseq/protocol/risks_and_limitations.md",
    "benchmark/chipseq/protocol/real_narrow_contig_amendment_20260830.md",
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
    parser.add_argument("--home", required=True, type=Path)
    parser.add_argument("--runtime", required=True, type=Path)
    parser.add_argument("--idr", required=True, type=Path)
    parser.add_argument("--java-home", required=True, type=Path)
    parser.add_argument("--r-bin", required=True, type=Path)
    parser.add_argument("--nextflow", required=True, type=Path)
    parser.add_argument("--git", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if "SLURM_JOB_ID" not in os.environ:
        raise RuntimeError("preflight must run in a Slurm allocation")

    repo = args.repo.resolve()
    git = str(args.git.resolve())
    head = command([git, "-C", str(repo), "rev-parse", "HEAD"])
    if command([git, "-C", str(repo), "rev-parse", SCIENTIFIC_TARGET]) != SCIENTIFIC_TARGET:
        raise ValueError("scientific target cannot be resolved")
    if command([git, "-C", str(repo), "merge-base", "HEAD", PROTOCOL_COMMIT]) != PROTOCOL_COMMIT:
        raise ValueError("frozen protocol is not an ancestor of the benchmark branch")
    if subprocess.run(
        [git, "-C", str(repo), "diff", "--quiet", SCIENTIFIC_TARGET, "--", *SCIENTIFIC_PATHS], check=False
    ).returncode:
        raise ValueError("scientific files differ from the target commit")

    config = json.loads((repo / "benchmark/chipseq/configs/real_narrow_execution.json").read_text(encoding="utf-8"))
    macs = json.loads((repo / "benchmark/chipseq/configs/macs3_parameters.json").read_text(encoding="utf-8"))
    frozen = {
        "benchmark_id": config["benchmark_id"] == "chipseq-real-narrow-k562-ctcf-v1",
        "scientific_target": config["scientific_target"] == SCIENTIFIC_TARGET,
        "dataset": config["dataset"]["replicate_files"] == ["ENCFF000BWM", "ENCFF000BWR"]
        and config["dataset"]["control_file"] == "ENCFF000BWK",
        "reference": config["reference"]["assembly"] == "GRCh38.p14"
        and config["reference"]["blacklist"] == "ENCFF356LFX",
        "macs3": macs["macs3_version"] == "3.0.4" and macs["arms"]["real_narrow"] == {
            "peak_type": "narrow", "format": "BAM", "effective_genome_size": 2913022398
        },
        "idr": config["processing"]["idr"] == {
            "version": "2.0.4.2", "rank": "signal_value", "threshold": 0.05, "seed": 0
        },
        "motif": config["evaluation"]["motif"]["matrix_id"] == "MA0139.1",
        "null_sets": config["evaluation"]["encode_overlap_null"]["sets"] == 100,
        "external_contig_policy": config["external_references"]["contig_policy"] == {
            "comparison_universe": "intersection of GENCODE FASTA and external-reference contigs",
            "absent_external_records": "exclude without renaming and report records plus covered bases",
            "null_universe": "same shared contigs as the observed comparison",
        },
    }
    if not all(frozen.values()):
        raise ValueError(f"frozen configuration mismatch: {frozen}")

    env = os.environ.copy()
    env["JAVA_HOME"] = str(args.java_home.resolve())
    env["NXF_VER"] = "25.10.7"
    env["PATH"] = os.pathsep.join(
        (str(args.java_home.resolve() / "bin"), str(args.runtime.resolve() / "bin"),
         str(args.idr.resolve() / "bin"), "/usr/bin", "/bin")
    )
    nextflow_output = command([str(args.nextflow), "-version"], env)
    nextflow_version = next(
        (line.strip() for line in nextflow_output.splitlines() if line.strip().lower().startswith("version ")), ""
    )
    versions = {
        "os": platform.platform(),
        "java": first_line(command([str(args.java_home / "bin/java"), "-version"], env)),
        "nextflow": nextflow_version,
        "slurm": command(["srun", "--version"], env),
        "python": command([str(args.runtime / "bin/python"), "--version"], env),
        "scipy": command([str(args.runtime / "bin/python"), "-c", "import scipy; print(scipy.__version__)"], env),
        "r": first_line(command([str(args.r_bin), "--version"], env)),
        "bowtie2": first_line(command([str(args.runtime / "bin/bowtie2"), "--version"], env)),
        "samtools": first_line(command([str(args.runtime / "bin/samtools"), "--version"], env)),
        "macs3": command([str(args.runtime / "bin/macs3"), "--version"], env),
        "idr": first_line(command([str(args.idr / "bin/idr"), "--version"], env)),
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
        "idr": versions["idr"] == "IDR 2.0.4.2",
        "fastqc": "v0.12.1" in versions["fastqc"],
        "multiqc": "1.35" in versions["multiqc"],
        "bedtools": "v2.31.1" in versions["bedtools"],
        "scipy": bool(versions["scipy"]),
    }
    if not all(expected.values()):
        raise ValueError(f"runtime version mismatch: {expected}; observed={versions}")

    scratch_usage = shutil.disk_usage(args.scratch)
    home_usage = shutil.disk_usage(args.home)
    protocol = {name: sha256(repo / name) for name in PROTOCOL_FILES}
    result = {
        "schema_version": "1.0",
        "type": "real_narrow_preflight",
        "status": "PASS",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "host": {
            "hostname": socket.getfqdn(),
            "platform": platform.platform(),
            "slurm_job_id": os.environ["SLURM_JOB_ID"],
        },
        "git": {
            "branch": command([git, "-C", str(repo), "branch", "--show-current"]),
            "head": head,
            "starting_commit": config["starting_commit"],
            "scientific_target": SCIENTIFIC_TARGET,
            "protocol_commit": PROTOCOL_COMMIT,
        },
        "checks": {
            "protocol": True,
            **frozen,
            **expected,
            "scratch_free": scratch_usage.free > 100_000_000_000,
            "home_free": home_usage.free > 10_000_000_000,
        },
        "versions": versions,
        "protocol_sha256": protocol,
        "storage": {
            "scratch": {"path": str(args.scratch.resolve()), "total_bytes": scratch_usage.total, "free_bytes": scratch_usage.free},
            "home": {"path": str(args.home.resolve()), "total_bytes": home_usage.total, "free_bytes": home_usage.free},
        },
    }
    if not all(result["checks"].values()):
        raise ValueError(f"preflight check failed: {result['checks']}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
