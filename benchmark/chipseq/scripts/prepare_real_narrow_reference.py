#!/usr/bin/env python3
"""Prepare and validate the frozen GRCh38 real-narrow reference bundle."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


EXPECTED_ROLES = {
    "genome_fasta",
    "annotation_gtf",
    "blacklist",
    "narrow_reference_peaks",
}


def digest(path: Path, algorithm: str = "sha256") -> str:
    value = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def decompress(source: Path, destination: Path) -> None:
    with gzip.open(source, "rb") as incoming, destination.open("wb") as outgoing:
        shutil.copyfileobj(incoming, outgoing, length=1024 * 1024)


def fai_contigs(path: Path) -> set[str]:
    contigs = set()
    for number, line in enumerate(path.read_text(encoding="ascii").splitlines(), start=1):
        fields = line.split("\t")
        if len(fields) < 5 or not fields[0]:
            raise ValueError(f"invalid FAI row {number}")
        if fields[0] in contigs:
            raise ValueError(f"duplicate FASTA contig: {fields[0]}")
        contigs.add(fields[0])
    if not contigs:
        raise ValueError("FASTA index contains no contigs")
    return contigs


def gtf_contigs(path: Path) -> set[str]:
    contigs = set()
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            if line.startswith("#"):
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) != 9:
                raise ValueError(f"invalid GTF row {number}")
            contigs.add(fields[0])
    if not contigs:
        raise ValueError("GTF contains no records")
    return contigs


def bed_contigs(path: Path, compressed: bool = False) -> set[str]:
    opener = gzip.open if compressed else Path.open
    kwargs = {"mode": "rt", "encoding": "utf-8"} if compressed else {"mode": "r", "encoding": "utf-8"}
    contigs = set()
    with opener(path, **kwargs) as handle:
        for number, line in enumerate(handle, start=1):
            if not line.strip() or line.startswith(("#", "track", "browser")):
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 3:
                raise ValueError(f"invalid BED row {number}: {path.name}")
            contigs.add(fields[0])
    if not contigs:
        raise ValueError(f"BED contains no records: {path.name}")
    return contigs


def artifact(path: Path, role: str, published_root: Path) -> dict[str, object]:
    return {
        "role": role,
        "path": str(published_root / path.name),
        "bytes": path.stat().st_size,
        "sha256": digest(path),
    }


def validate_existing(manifest_path: Path) -> int:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "REFERENCE_READY":
        raise ValueError("reference manifest is not REFERENCE_READY")
    for entry in manifest.get("artifacts", []):
        path = Path(entry["path"])
        if not path.is_file() or path.stat().st_size != entry["bytes"] or digest(path) != entry["sha256"]:
            raise ValueError(f"reference artifact failed validation: {path}")
    print(json.dumps({"status": "REFERENCE_READY", "validated": len(manifest["artifacts"])}))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download-manifest", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--samtools", type=Path)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--validate-existing", action="store_true")
    args = parser.parse_args()

    if args.validate_existing:
        return validate_existing(args.manifest)
    if "SLURM_JOB_ID" not in os.environ:
        raise RuntimeError("reference preparation must run in a Slurm allocation")
    if args.download_manifest is None or args.output_dir is None or args.samtools is None:
        parser.error("--download-manifest, --output-dir and --samtools are required")
    if args.output_dir.exists() or args.manifest.exists():
        raise FileExistsError("reference output already exists")

    download = json.loads(args.download_manifest.read_text(encoding="utf-8"))
    if download.get("status") != "DOWNLOAD_CHECKSUM_VALIDATED":
        raise ValueError("download manifest is not validated")
    by_role = {entry["role"]: entry for entry in download["artifacts"] if entry["role"] in EXPECTED_ROLES}
    if set(by_role) != EXPECTED_ROLES:
        raise ValueError(f"missing frozen reference roles: {EXPECTED_ROLES.difference(by_role)}")

    for entry in by_role.values():
        source = Path(entry["path"])
        if not source.is_file() or source.stat().st_size != entry["size_bytes"]:
            raise ValueError(f"source size mismatch: {source}")
        if digest(source) != entry["sha256"]:
            raise ValueError(f"source checksum mismatch: {source}")

    args.output_dir.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".real-narrow-reference.", dir=args.output_dir.parent))
    try:
        genome = stage / "genome.fa"
        annotation = stage / "annotation.gtf"
        blacklist = stage / "blacklist.bed"
        decompress(Path(by_role["genome_fasta"]["path"]), genome)
        decompress(Path(by_role["annotation_gtf"]["path"]), annotation)
        decompress(Path(by_role["blacklist"]["path"]), blacklist)

        completed = subprocess.run(
            [str(args.samtools), "faidx", str(genome)], capture_output=True, text=True, check=False
        )
        if completed.returncode:
            raise RuntimeError(f"samtools faidx failed: {completed.stderr.strip()}")
        fai = Path(f"{genome}.fai")

        fasta_names = fai_contigs(fai)
        sets = {
            "gtf": gtf_contigs(annotation),
            "blacklist": bed_contigs(blacklist),
            "encode_reference_peaks": bed_contigs(Path(by_role["narrow_reference_peaks"]["path"]), True),
        }
        missing = {name: sorted(values.difference(fasta_names)) for name, values in sets.items() if values - fasta_names}
        if missing:
            raise ValueError(f"reference contig mismatch: {missing}")

        version = subprocess.run(
            [str(args.samtools), "--version"], capture_output=True, text=True, check=True
        ).stdout.splitlines()[0]
        manifest = {
            "schema_version": "1.0",
            "type": "chipseq_real_narrow_reference",
            "status": "REFERENCE_READY",
            "bundle_id": "gencode_human_v50_primary",
            "release": "GENCODE_50",
            "assembly": "GRCh38.p14",
            "contig_policy": "GENCODE names unchanged",
            "effective_genome_size": 2913022398,
            "slurm_job_id": os.environ["SLURM_JOB_ID"],
            "samtools": version,
            "sources": list(by_role.values()),
            "contigs": {"fasta": len(fasta_names), **{name: len(values) for name, values in sets.items()}},
            "artifacts": [
                artifact(genome, "genome_fasta", args.output_dir),
                artifact(fai, "genome_fai", args.output_dir),
                artifact(annotation, "annotation_gtf", args.output_dir),
                artifact(blacklist, "blacklist", args.output_dir),
            ],
            "command": " ".join(sys.argv),
        }
        (stage / "reference_manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
        )
        os.replace(stage, args.output_dir)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise

    print(json.dumps({"status": "REFERENCE_READY", "contigs": manifest["contigs"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
