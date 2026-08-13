#!/usr/bin/env python3
import argparse
import base64
import hashlib
import json
import os
import re
import sys


DEFAULTS = {
    "provider": "python_interval_v1",
    "mode": "overlap_priority",
    "overlap_mode": "any",
    "promoter_upstream": 2000,
    "promoter_downstream": 500,
    "max_tss_distance": None,
    "feature_priority": ["promoter", "exon", "intron", "downstream", "gene"],
    "gene_assignment": "first",
    "strand_aware": False,
    "intergenic_policy": "retain",
}
FEATURES = {"promoter", "exon", "intron", "downstream", "gene"}


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path, label):
    with open(path, encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{label} must contain a JSON object")
    return value


def safe_id(value, label):
    value = str(value or "")
    if not value or not re.fullmatch(r"[A-Za-z0-9._-]+", value):
        raise ValueError(f"invalid or empty {label}: {value!r}")
    return value


def parse_fasta_contigs(path):
    result = set()
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if line.startswith(">"):
                name = line[1:].strip().split()[0]
                if not name or name in result:
                    raise ValueError(f"reference has empty or duplicate contig {name!r}")
                result.add(name)
    if not result:
        raise ValueError("reference contains no FASTA contigs")
    return result


def parse_annotation_contigs(path):
    result = set()
    with open(path, encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip() or line.startswith("#"):
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) != 9:
                raise ValueError(f"annotation line {line_number}: expected 9 GTF/GFF columns")
            try:
                start, end = int(fields[3]), int(fields[4])
            except ValueError as error:
                raise ValueError(f"annotation line {line_number}: invalid coordinates: {error}")
            if start < 1 or end < start:
                raise ValueError(f"annotation line {line_number}: invalid one-based coordinates")
            result.add(fields[0])
    if not result:
        raise ValueError("annotation contains no features")
    return result


def parse_peak_contigs(path):
    result, rows = set(), 0
    with open(path, encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 3:
                raise ValueError(f"peak line {line_number}: expected at least 3 columns")
            try:
                start, end = int(fields[1]), int(fields[2])
            except ValueError as error:
                raise ValueError(f"peak line {line_number}: invalid coordinates: {error}")
            if start < 0 or end <= start:
                raise ValueError(f"peak line {line_number}: invalid half-open coordinates")
            if not fields[0] or any(char.isspace() for char in fields[0]):
                raise ValueError(f"peak line {line_number}: invalid contig")
            result.add(fields[0])
            rows += 1
    return result, rows


def artifact_checksum(document, preferred):
    artifacts = document.get("artifacts", {})
    for role in preferred:
        artifact = artifacts.get(role)
        if isinstance(artifact, dict) and artifact.get("available", True):
            return artifact.get("sha256")
    return None


def validate_spec(raw):
    spec = dict(DEFAULTS)
    spec.update(raw or {})
    if spec["provider"] != "python_interval_v1":
        raise ValueError(f"unsupported peak annotation provider {spec['provider']!r}")
    if spec["mode"] != "overlap_priority" or spec["overlap_mode"] != "any":
        raise ValueError("v1 supports only mode=overlap_priority and overlap_mode=any")
    if spec["max_tss_distance"] is not None:
        raise ValueError("python_interval_v1 does not implement nearest-TSS assignment")
    for key in ("promoter_upstream", "promoter_downstream"):
        if isinstance(spec[key], bool) or not isinstance(spec[key], int) or spec[key] < 0:
            raise ValueError(f"{key} must be a non-negative integer")
    priority = spec["feature_priority"]
    if not isinstance(priority, list) or set(priority) != FEATURES or len(priority) != len(FEATURES):
        raise ValueError("feature_priority must contain each supported category exactly once")
    if spec["gene_assignment"] not in {"first", "all"}:
        raise ValueError("gene_assignment must be first or all")
    if spec["strand_aware"] is not False:
        raise ValueError("python_interval_v1 supports strand_aware=false only")
    if spec["intergenic_policy"] not in {"retain", "drop"}:
        raise ValueError("intergenic_policy must be retain or drop")
    return spec


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--meta-base64", required=True)
    parser.add_argument("--peaks", required=True)
    parser.add_argument("--peak-manifest", required=True)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--reference-manifest", required=True)
    parser.add_argument("--annotation", required=True)
    parser.add_argument("--spec-base64", required=True)
    parser.add_argument("--request", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    try:
        meta = json.loads(base64.b64decode(args.meta_base64).decode("utf-8"))
        spec = validate_spec(json.loads(base64.b64decode(args.spec_base64).decode("utf-8")))
        peak_doc = load_json(args.peak_manifest, "peak manifest")
        ref_doc = load_json(args.reference_manifest, "reference manifest")
        source_type = peak_doc.get("type")
        if source_type not in {"peak_calling", "consensus", "idr"}:
            raise ValueError(f"unsupported peak manifest type {source_type!r}")
        source_id = safe_id(peak_doc.get("id"), "peak manifest id")
        request_id = safe_id(meta.get("id"), "annotation id")
        if meta.get("source_id") != source_id:
            raise ValueError("metadata source_id does not match peak manifest id")
        genome_id = safe_id(peak_doc.get("genome_id") or meta.get("genome_id"), "genome_id")
        ref_genome = safe_id(ref_doc.get("genome_id") or ref_doc.get("build"), "reference genome/build")
        if genome_id != ref_genome:
            raise ValueError(f"genome/build mismatch: peaks={genome_id!r}, reference={ref_genome!r}")
        build = str(ref_doc.get("build") or ref_genome)
        if str(meta.get("genome_id")) != genome_id:
            raise ValueError("metadata genome_id does not match peak manifest")
        peak_sha = sha256(args.peaks)
        expected_peak_sha = artifact_checksum(peak_doc, ("peaks", "consolidated_bed", "consolidated_peaks"))
        if expected_peak_sha and expected_peak_sha != peak_sha:
            raise ValueError("peak artifact checksum does not match peak manifest")
        ref_sha = sha256(args.reference)
        expected_ref_sha = artifact_checksum(ref_doc, ("reference", "fasta", "genome"))
        if expected_ref_sha and expected_ref_sha != ref_sha:
            raise ValueError("reference checksum does not match reference manifest")
        reference_contigs = parse_fasta_contigs(args.reference)
        annotation_contigs = parse_annotation_contigs(args.annotation)
        peak_contigs, peak_count = parse_peak_contigs(args.peaks)
        missing_annotation = annotation_contigs - reference_contigs
        missing_peaks = peak_contigs - reference_contigs
        if missing_annotation:
            raise ValueError("annotation contigs absent from reference: " + ",".join(sorted(missing_annotation)[:20]))
        if missing_peaks:
            raise ValueError("peak contigs absent from reference: " + ",".join(sorted(missing_peaks)[:20]))
        if peak_contigs and not peak_contigs.intersection(annotation_contigs):
            raise ValueError("peak and annotation seqnames have no overlap")
        record_ids = []
        sample_ids = []
        if source_type == "peak_calling":
            record_ids = [safe_id(peak_doc.get("record_id"), "record_id")]
            sample_ids = [safe_id(peak_doc.get("sample_id"), "sample_id")]
        else:
            replicates = peak_doc.get("replicates", [])
            if not replicates:
                raise ValueError("consensus manifest has no replicate identity")
            record_ids = [safe_id(item.get("record_id"), "record_id") for item in replicates]
            sample_ids = [safe_id(item.get("sample_id"), "sample_id") for item in replicates]
        if len(record_ids) != len(set(record_ids)):
            raise ValueError("duplicate record_id in source manifest")
        request = {
            "schema_version": "1.0", "type": "peak_annotation_request", "id": request_id,
            "source_type": source_type, "source_id": source_id,
            "record_id": record_ids[0] if len(record_ids) == 1 else None,
            "record_ids": record_ids, "sample_ids": sample_ids,
            "dataset": peak_doc.get("dataset"), "experiment_id": peak_doc.get("experiment_id"),
            "target": peak_doc.get("target"), "genome_id": genome_id, "build": build,
            "organism": meta.get("organism") or ref_doc.get("organism"),
            "peak_type": peak_doc.get("peak_type") or "bed", "provider": spec.pop("provider"),
            "provider_version": "1.0.0", "parameters": spec, "inputs": {
                "peaks": {"name": os.path.basename(args.peaks), "sha256": peak_sha, "rows": peak_count},
                "peak_manifest": {"name": os.path.basename(args.peak_manifest), "sha256": sha256(args.peak_manifest)},
                "reference": {"name": os.path.basename(args.reference), "sha256": ref_sha},
                "reference_manifest": {"name": os.path.basename(args.reference_manifest), "sha256": sha256(args.reference_manifest)},
                "annotation": {"name": os.path.basename(args.annotation), "sha256": sha256(args.annotation)},
            }, "seqnames": {"peaks": sorted(peak_contigs), "annotation": sorted(annotation_contigs), "reference": sorted(reference_contigs)},
            "status": "valid",
        }
        with open(args.request, "w", encoding="utf-8") as handle:
            json.dump(request, handle, indent=2, sort_keys=True); handle.write("\n")
        with open(args.report, "w", encoding="utf-8") as handle:
            json.dump({"schema_version": "1.0", "id": request_id, "checks": {"identity": "pass", "coordinates": "pass", "seqnames": "pass", "checksums": "pass", "parameters": "pass"}, "status": "valid"}, handle, indent=2, sort_keys=True); handle.write("\n")
    except (ValueError, KeyError, json.JSONDecodeError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
