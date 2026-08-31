#!/usr/bin/env python3
"""Prepare and validate the frozen GRCh38 Real Broad reference bundle."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from prepare_real_narrow_reference import (
    artifact,
    bed_statistics,
    decompress,
    digest,
    fai_contigs,
    gtf_contigs,
    validate_existing,
)


EXPECTED_ROLES = {"genome_fasta", "annotation_gtf", "blacklist", "broad_reference_peaks"}


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
        if not source.is_file() or source.stat().st_size != entry["size_bytes"] or digest(source) != entry["sha256"]:
            raise ValueError(f"source identity mismatch: {source}")

    args.output_dir.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".real-broad-reference.", dir=args.output_dir.parent))
    try:
        genome = stage / "genome.fa"
        annotation = stage / "annotation.gtf"
        blacklist = stage / "blacklist.bed"
        decompress(Path(by_role["genome_fasta"]["path"]), genome)
        decompress(Path(by_role["annotation_gtf"]["path"]), annotation)
        decompress(Path(by_role["blacklist"]["path"]), blacklist)

        completed = subprocess.run([str(args.samtools), "faidx", str(genome)], capture_output=True, text=True, check=False)
        if completed.returncode:
            raise RuntimeError(f"samtools faidx failed: {completed.stderr.strip()}")
        fai = Path(f"{genome}.fai")
        fasta_names = fai_contigs(fai)
        blacklist_stats = bed_statistics(blacklist)
        external_stats = bed_statistics(Path(by_role["broad_reference_peaks"]["path"]), True)
        sets = {"gtf": gtf_contigs(annotation), "blacklist": set(blacklist_stats)}
        missing = {name: sorted(values - fasta_names) for name, values in sets.items() if values - fasta_names}
        if missing:
            raise ValueError(f"reference contig mismatch: {missing}")
        external_absent = sorted(set(external_stats) - fasta_names)
        excluded = {name: external_stats[name] for name in external_absent}
        samtools_version = subprocess.run(
            [str(args.samtools), "--version"], capture_output=True, text=True, check=True
        ).stdout.splitlines()[0]
        manifest = {
            "schema_version": "1.0",
            "type": "chipseq_real_broad_reference",
            "status": "REFERENCE_READY",
            "bundle_id": "gencode_human_v50_primary",
            "release": "GENCODE_50",
            "assembly": "GRCh38.p14",
            "contig_policy": "GENCODE names unchanged",
            "effective_genome_size": 2913022398,
            "slurm_job_id": os.environ["SLURM_JOB_ID"],
            "samtools": samtools_version,
            "sources": list(by_role.values()),
            "contigs": {"fasta": len(fasta_names), **{name: len(values) for name, values in sets.items()}},
            "external_reference_contig_policy": {
                "comparison_universe": "intersection of GENCODE FASTA and external-reference contigs",
                "renaming": "prohibited",
                "external_contigs": len(external_stats),
                "shared_contigs": len(set(external_stats) & fasta_names),
                "excluded_contigs": excluded,
                "excluded_records": sum(value["records"] for value in excluded.values()),
                "excluded_covered_bases": sum(value["covered_bases"] for value in excluded.values()),
            },
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
