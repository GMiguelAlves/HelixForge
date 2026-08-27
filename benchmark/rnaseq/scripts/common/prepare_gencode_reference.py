#!/usr/bin/env python3
"""Build the frozen GENCODE 49 primary-assembly RNA-seq reference bundle."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
import re
import shutil
import sys
from collections import OrderedDict
from pathlib import Path


ATTR_RE = re.compile(r'([A-Za-z][A-Za-z0-9_]*) "([^"]*)";')
EXPECTED_ROLES = {"annotation", "transcripts", "genome"}


def digest(path: Path, algorithm: str = "sha256") -> str:
    value = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def parse_registry(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    if len(rows) != 3 or {row["role"] for row in rows} != EXPECTED_ROLES:
        raise ValueError("reference registry must contain exactly annotation, transcripts and genome")
    identities = {(row["bundle_id"], row["release"], row["assembly"]) for row in rows}
    if identities != {("gencode_human_v49_primary", "GENCODE_49", "GRCh38.p14")}:
        raise ValueError(f"unexpected frozen reference identity: {identities}")
    for row in rows:
        if Path(row["url"]).name != row["filename"]:
            raise ValueError(f"URL/filename mismatch for {row['role']}")
        if row["upstream_checksum_source"] != "release_49 MD5SUMS":
            raise ValueError("reference registry must use the official release_49 MD5SUMS")
    return {row["role"]: row for row in rows}


def parse_md5s(path: Path) -> dict[str, str]:
    checksums: dict[str, str] = {}
    for number, line in enumerate(path.read_text(encoding="ascii").splitlines(), start=1):
        fields = line.split()
        if not fields:
            continue
        if len(fields) != 2 or not re.fullmatch(r"[0-9a-f]{32}", fields[0]):
            raise ValueError(f"invalid MD5SUMS line {number}")
        checksums[fields[1].lstrip("*")] = fields[0]
    return checksums


def parse_attributes(text: str) -> dict[str, str]:
    return dict(ATTR_RE.findall(text))


def copy_annotation_and_mapping(source: Path, destination: Path) -> OrderedDict[str, str]:
    mapping: OrderedDict[str, str] = OrderedDict()
    with gzip.open(source, "rt", encoding="utf-8") as incoming, destination.open(
        "w", encoding="utf-8", newline="\n"
    ) as outgoing:
        for number, line in enumerate(incoming, start=1):
            outgoing.write(line)
            if line.startswith("#"):
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) != 9:
                raise ValueError(f"invalid GTF row {number}")
            if fields[2] != "transcript":
                continue
            attributes = parse_attributes(fields[8])
            transcript = attributes.get("transcript_id")
            gene = attributes.get("gene_id")
            if not transcript or not gene:
                raise ValueError(f"missing transcript_id/gene_id in GTF row {number}")
            previous = mapping.setdefault(transcript, gene)
            if previous != gene:
                raise ValueError(f"transcript maps to multiple genes: {transcript}")
    if not mapping:
        raise ValueError("primary GTF contains no transcript features")
    return mapping


def filter_transcriptome(source: Path, destination: Path, mapping: OrderedDict[str, str]) -> int:
    seen: set[str] = set()
    retained = 0
    keep = False
    with gzip.open(source, "rt", encoding="ascii") as incoming, destination.open(
        "w", encoding="ascii", newline="\n"
    ) as outgoing:
        for number, line in enumerate(incoming, start=1):
            if line.startswith(">"):
                token = line[1:].strip().split(maxsplit=1)[0]
                transcript = token.split("|", 1)[0]
                if not transcript:
                    raise ValueError(f"empty FASTA identifier at line {number}")
                if transcript in seen:
                    raise ValueError(f"duplicate transcript FASTA identifier: {transcript}")
                seen.add(transcript)
                keep = transcript in mapping
                if keep:
                    outgoing.write(f">{transcript}\n")
                    retained += 1
            elif keep:
                sequence = line.strip()
                if not sequence:
                    raise ValueError(f"empty sequence row at line {number}")
                outgoing.write(sequence + "\n")
    missing = set(mapping).difference(seen)
    if missing:
        examples = ", ".join(sorted(missing)[:10])
        raise ValueError(f"{len(missing)} primary-GTF transcripts absent from FASTA: {examples}")
    if retained != len(mapping):
        raise ValueError("retained transcript count does not match tx2gene universe")
    return retained


def copy_gzip(source: Path, destination: Path) -> None:
    with gzip.open(source, "rb") as incoming, destination.open("wb") as outgoing:
        shutil.copyfileobj(incoming, outgoing, length=1024 * 1024)


def artifact(
    path: Path, role: str, records: int | None = None, published_path: Path | None = None
) -> dict[str, object]:
    result: dict[str, object] = {
        "role": role,
        "path": str(published_path or path),
        "bytes": path.stat().st_size,
        "sha256": digest(path),
    }
    if records is not None:
        result["records"] = records
    return result


def validate_existing(manifest_path: Path) -> int:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "REFERENCE_READY":
        raise ValueError("reference manifest is not REFERENCE_READY")
    for entry in manifest["artifacts"]:
        path = Path(entry["path"])
        if not path.is_file() or path.stat().st_size != entry["bytes"] or digest(path) != entry["sha256"]:
            raise ValueError(f"reference artifact failed validation: {path}")
    print(json.dumps({"status": "REFERENCE_READY", "validated": len(manifest["artifacts"])}))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--sources-dir", type=Path)
    parser.add_argument("--md5s", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--published-dir", type=Path)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--validate-existing", action="store_true")
    args = parser.parse_args()
    if args.validate_existing:
        return validate_existing(args.manifest)
    if not os.environ.get("SLURM_JOB_ID"):
        raise SystemExit("reference preparation must execute inside a Slurm job")
    for name in ("registry", "sources_dir", "md5s", "output_dir", "published_dir"):
        if getattr(args, name) is None:
            parser.error(f"--{name.replace('_', '-')} is required")
    if args.output_dir.exists() or args.manifest.exists():
        raise FileExistsError("reference output already exists")

    registry = parse_registry(args.registry)
    upstream_md5 = parse_md5s(args.md5s)
    sources: dict[str, Path] = {}
    source_docs = []
    for role, row in registry.items():
        path = args.sources_dir / row["filename"]
        if not path.is_file():
            raise FileNotFoundError(path)
        expected = upstream_md5.get(row["filename"])
        if not expected:
            raise ValueError(f"upstream MD5 absent for {row['filename']}")
        observed = digest(path, "md5")
        if observed != expected:
            raise ValueError(f"upstream MD5 mismatch for {row['filename']}")
        sources[role] = path
        source_docs.append({
            "role": role, "filename": row["filename"], "url": row["url"],
            "bytes": path.stat().st_size, "md5": observed, "sha256": digest(path),
            "derivation": row["derivation"],
        })

    args.output_dir.mkdir(parents=True)
    annotation = args.output_dir / "annotation.gtf"
    transcriptome = args.output_dir / "transcriptome.fa"
    genome = args.output_dir / "genome.fa"
    tx2gene = args.output_dir / "tx2gene.tsv"
    mapping = copy_annotation_and_mapping(sources["annotation"], annotation)
    retained = filter_transcriptome(sources["transcripts"], transcriptome, mapping)
    copy_gzip(sources["genome"], genome)
    with tx2gene.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("transcript_id\tgene_id\n")
        for transcript, gene in mapping.items():
            handle.write(f"{transcript}\t{gene}\n")

    artifacts = [
        artifact(annotation, "annotation", len(mapping), args.published_dir / annotation.name),
        artifact(transcriptome, "transcriptome", retained, args.published_dir / transcriptome.name),
        artifact(genome, "genome", published_path=args.published_dir / genome.name),
        artifact(tx2gene, "tx2gene", len(mapping), args.published_dir / tx2gene.name),
    ]
    manifest = {
        "schema_version": "1.0",
        "status": "REFERENCE_READY",
        "bundle_id": "gencode_human_v49_primary",
        "release": "GENCODE_49",
        "assembly": "GRCh38.p14",
        "id_policy": {
            "versioned_ids": True,
            "ignoreTxVersion": False,
            "ignoreAfterBar": False,
            "transcript_fasta_header": "first pipe-delimited token",
            "transcript_filter": "transcript_id present in primary-assembly GTF",
        },
        "transcripts": retained,
        "genes": len(set(mapping.values())),
        "slurm_job_id": os.environ["SLURM_JOB_ID"],
        "sources": source_docs,
        "md5s": {"url": "https://ftp.ebi.ac.uk/pub/databases/gencode/Gencode_human/release_49/MD5SUMS",
                 "sha256": digest(args.md5s)},
        "artifacts": artifacts,
        "command": " ".join(sys.argv),
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "REFERENCE_READY", "transcripts": retained, "genes": manifest["genes"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
