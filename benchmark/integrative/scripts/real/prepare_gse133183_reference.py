#!/usr/bin/env python3
"""Build the frozen GENCODE 50/GRCh38.p14 reference bundle."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any


EXPECTED = {"genome_fasta", "annotation_gtf", "transcriptome", "blacklist"}


def digest(path: Path, algorithm: str = "sha256") -> str:
    value = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def read_registry(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def decompress(source: Path, destination: Path) -> None:
    with gzip.open(source, "rb") as input_handle, destination.open("wb") as output_handle:
        shutil.copyfileobj(input_handle, output_handle, length=8 * 1024 * 1024)


def annotation_contigs(path: Path) -> set[str]:
    result: set[str] = set()
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("#"):
                continue
            result.add(line.split("\t", 1)[0])
    return result


def bed_contigs(path: Path) -> set[str]:
    result: set[str] = set()
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip() and not line.startswith(("#", "track", "browser")):
                result.add(line.split("\t", 1)[0])
    return result


def artifact(path: Path, role: str, root: Path) -> dict[str, Any]:
    return {
        "role": role,
        "filename": path.name,
        "path": str(path),
        "relative_path": str(path.relative_to(root)),
        "size_bytes": path.stat().st_size,
        "sha256": digest(path),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--sources-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--samtools", required=True, type=Path)
    args = parser.parse_args()
    if not os.environ.get("SLURM_JOB_ID"):
        raise SystemExit("reference preparation must execute inside a Slurm job")
    if args.output_dir.exists() or args.manifest.exists():
        raise FileExistsError("reference bundle or manifest already exists")

    rows = read_registry(args.registry)
    by_role = {row["role"]: row for row in rows}
    if set(by_role) != EXPECTED or len(rows) != 4:
        raise ValueError("reference registry is not the frozen four-artifact bundle")
    for row in rows:
        if row["release_or_accession"] not in {"release_50", "ENCFF356LFX"}:
            raise ValueError(f"unexpected reference release: {row}")
        source = args.sources_dir / row["filename"]
        if not source.is_file() or digest(source, "md5") != row["frozen_md5"]:
            raise ValueError(f"source MD5 mismatch: {source}")

    args.output_dir.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".gencode50-reference.", dir=args.output_dir.parent))
    try:
        genome = stage / "genome.fa"
        annotation = stage / "annotation.gtf"
        transcriptome = stage / "transcriptome.fa"
        blacklist = stage / "blacklist.bed"
        decompress(args.sources_dir / by_role["genome_fasta"]["filename"], genome)
        decompress(args.sources_dir / by_role["annotation_gtf"]["filename"], annotation)
        decompress(args.sources_dir / by_role["transcriptome"]["filename"], transcriptome)
        decompress(args.sources_dir / by_role["blacklist"]["filename"], blacklist)
        completed = subprocess.run([str(args.samtools), "faidx", str(genome)], capture_output=True, text=True)
        if completed.returncode:
            raise RuntimeError(f"samtools faidx failed: {completed.stderr.strip()}")
        fai = Path(f"{genome}.fai")
        fasta_contigs = {line.split("\t", 1)[0] for line in fai.read_text(encoding="utf-8").splitlines() if line}
        missing_gtf = annotation_contigs(annotation) - fasta_contigs
        missing_blacklist = bed_contigs(blacklist) - fasta_contigs
        if missing_gtf or missing_blacklist:
            raise ValueError({"gtf_contigs_missing": sorted(missing_gtf), "blacklist_contigs_missing": sorted(missing_blacklist)})
        published_paths = {
            "genome_fasta": args.output_dir / genome.name,
            "genome_fai": args.output_dir / fai.name,
            "annotation_gtf": args.output_dir / annotation.name,
            "transcriptome": args.output_dir / transcriptome.name,
            "blacklist": args.output_dir / blacklist.name,
        }
        manifest = {
            "schema_version": "1.0",
            "type": "helixforge_integrative_real_reference_bundle",
            "status": "REFERENCE_READY",
            "bundle_id": "gencode_human_v50_primary",
            "release": "GENCODE_50",
            "assembly": "GRCh38.p14",
            "blacklist_accession": "ENCFF356LFX",
            "slurm_job_id": os.environ["SLURM_JOB_ID"],
            "samtools": completed.args[0],
            "contigs": {"fasta": len(fasta_contigs), "gtf": len(annotation_contigs(annotation)), "blacklist": len(bed_contigs(blacklist))},
            "sources": [
                {**row, "path": str(args.sources_dir / row["filename"]), "observed_md5": digest(args.sources_dir / row["filename"], "md5")}
                for row in rows
            ],
        }
        os.replace(stage, args.output_dir)
        manifest["artifacts"] = [artifact(path, role, args.output_dir) for role, path in published_paths.items()]
        args.manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except Exception:
        if stage.exists():
            shutil.rmtree(stage, ignore_errors=True)
        raise
    print(json.dumps({"status": "REFERENCE_READY", "artifacts": len(manifest["artifacts"]), "contigs": manifest["contigs"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
