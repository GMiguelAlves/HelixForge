#!/usr/bin/env python3
"""Normalize the derived GENCODE transcriptome to the frozen exact-ID policy."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import tempfile
from collections import OrderedDict
from pathlib import Path


ATTR_RE = re.compile(r'(\S+) "([^"]*)";')


def digest(path: Path, algorithm: str = "sha256") -> str:
    value = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def mapping_from_gtf(path: Path) -> OrderedDict[str, str]:
    mapping: OrderedDict[str, str] = OrderedDict()
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            if line.startswith("#"):
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) != 9:
                raise ValueError(f"invalid GTF row {number}")
            if fields[2] != "transcript":
                continue
            attrs = dict(ATTR_RE.findall(fields[8]))
            transcript, gene = attrs.get("transcript_id"), attrs.get("gene_id")
            if not transcript or not gene:
                raise ValueError(f"missing transcript/gene ID at GTF row {number}")
            previous = mapping.setdefault(transcript, gene)
            if previous != gene:
                raise ValueError(f"transcript maps to multiple genes: {transcript}")
    if not mapping:
        raise ValueError("annotation contains no transcript records")
    return mapping


def normalize(source: Path, destination: Path, mapping: OrderedDict[str, str]) -> int:
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
                if not transcript or transcript in seen:
                    raise ValueError(f"invalid or duplicate FASTA ID at line {number}: {transcript}")
                seen.add(transcript)
                keep = transcript in mapping
                if keep:
                    outgoing.write(f">{transcript}\n")
                    retained += 1
            elif keep:
                sequence = line.strip()
                if not sequence:
                    raise ValueError(f"empty sequence at line {number}")
                outgoing.write(sequence + "\n")
    missing = set(mapping).difference(seen)
    if missing:
        raise ValueError(f"{len(missing)} GTF transcripts are absent from the official FASTA")
    if retained != len(mapping):
        raise ValueError("retained transcript count differs from the GTF mapping")
    return retained


def artifact(path: Path) -> dict[str, object]:
    return {"path": str(path), "sha256": digest(path), "size_bytes": path.stat().st_size}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--repo-commit", required=True)
    args = parser.parse_args()
    if not os.environ.get("SLURM_JOB_ID"):
        raise SystemExit("transcriptome normalization must execute inside a Slurm job")
    reference_root = args.root / "reference"
    bundle = reference_root / "bundle"
    source = reference_root / "sources/gencode.v50.transcripts.fa.gz"
    transcriptome = bundle / "transcriptome.fa"
    annotation = bundle / "annotation.gtf"
    manifest_path = reference_root / "reference_manifest.json"
    correction_path = reference_root / "transcriptome_normalization.json"
    if correction_path.exists():
        raise FileExistsError("transcriptome normalization was already applied")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    original = next(item for item in manifest["artifacts"] if item["role"] == "transcriptome")
    if digest(transcriptome) != original["sha256"]:
        raise ValueError("current transcriptome differs from its frozen manifest")
    source_entry = next(item for item in manifest["sources"] if item["role"] == "transcriptome")
    if digest(source, "md5") != source_entry["frozen_md5"]:
        raise ValueError("official transcript FASTA failed its frozen MD5")

    mapping = mapping_from_gtf(annotation)
    with tempfile.NamedTemporaryFile(
        mode="w", dir=bundle, prefix=".transcriptome.normalized.", delete=False
    ) as handle:
        staged = Path(handle.name)
    staged.unlink()
    try:
        retained = normalize(source, staged, mapping)
        normalized = artifact(staged)
        staged.replace(transcriptome)
    finally:
        staged.unlink(missing_ok=True)
    normalized = artifact(transcriptome)
    for index, item in enumerate(manifest["artifacts"]):
        if item["role"] == "transcriptome":
            manifest["artifacts"][index] = {
                **item, "sha256": normalized["sha256"], "size_bytes": normalized["size_bytes"]
            }
    transformation = {
        "status": "COMPLETE", "slurm_job_id": os.environ["SLURM_JOB_ID"],
        "repository_commit": args.repo_commit, "source": str(source),
        "source_md5": source_entry["frozen_md5"], "original_derived_sha256": original["sha256"],
        "normalized_sha256": normalized["sha256"], "transcripts": retained,
        "genes": len(set(mapping.values())), "header_policy": "first pipe-delimited token",
        "filter_policy": "transcript_id present in primary-assembly GTF",
        "ignoreTxVersion": False, "ignoreAfterBar": False,
    }
    manifest["id_policy"] = {
        "versioned_ids": True, "ignoreTxVersion": False, "ignoreAfterBar": False,
        "transcript_fasta_header": transformation["header_policy"],
        "transcript_filter": transformation["filter_policy"],
    }
    manifest["transcripts"] = retained
    manifest["genes"] = transformation["genes"]
    manifest.setdefault("transformations", []).append(transformation)
    manifest["slurm_job_id_latest_correction"] = os.environ["SLURM_JOB_ID"]
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")

    for case_name in ("rnaseq", "chipseq_h3k27me3", "chipseq_h3k27ac"):
        case_manifest_path = args.root / "cases" / case_name / "input_manifest.json"
        case_manifest = json.loads(case_manifest_path.read_text(encoding="utf-8"))
        case_manifest["artifacts"]["reference_manifest"] = artifact(manifest_path)
        case_manifest["reference_correction"] = {
            "status": "APPLIED_PRE_IMPORT" if case_name == "rnaseq" else "RECORDED_NO_CHIPSEQ_INPUT_CHANGE",
            "manifest": str(correction_path), "slurm_job_id": os.environ["SLURM_JOB_ID"],
        }
        case_manifest_path.write_text(
            json.dumps(case_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
        )
    correction_path.write_text(json.dumps({
        "schema_version": "1.0", "type": "gencode_transcriptome_normalization",
        **transformation, "artifact": normalized,
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"status": "COMPLETE", "transcripts": retained, "genes": transformation["genes"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
