#!/usr/bin/env python3
import argparse
import base64
import hashlib
import json
import math
import os
import sys


EXPECTED_COLUMNS = {"narrow": 10, "broad": 9}
FILTER_BITS = {
    "exclude_unmapped": 4,
    "exclude_secondary": 256,
    "exclude_qc_fail": 512,
    "exclude_supplementary": 2048,
}


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require_file(path, label, allow_empty=False):
    if not path or not os.path.isfile(path) or (not allow_empty and os.path.getsize(path) == 0):
        raise ValueError(f"{label} is missing or empty: {path}")


def load_json(path, label):
    require_file(path, label)
    with open(path, encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{label} must contain a JSON object")
    return value


def fasta_lengths(path):
    lengths, name, length = {}, None, 0
    with open(path, encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if line.startswith(">"):
                if name is not None:
                    lengths[name] = length
                name = line[1:].split()[0]
                if not name or name in lengths:
                    raise ValueError(f"reference line {line_number}: invalid or duplicate sequence name")
                length = 0
            else:
                if name is None:
                    raise ValueError("reference sequence appears before the first FASTA header")
                length += len(line.strip())
    if name is not None:
        lengths[name] = length
    if not lengths or any(value <= 0 for value in lengths.values()):
        raise ValueError("reference FASTA contains no non-empty sequences")
    return lengths


def validate_peaks(path, peak_type, reference_lengths):
    expected = EXPECTED_COLUMNS[peak_type]
    count, contigs = 0, set()
    with open(path, encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            columns = line.rstrip("\n").split("\t")
            if len(columns) != expected:
                raise ValueError(f"peak line {line_number}: {peak_type}Peak requires {expected} columns, found {len(columns)}")
            contig = columns[0]
            try:
                start, end = int(columns[1]), int(columns[2])
                float(columns[4])
                float(columns[6])
            except ValueError as error:
                raise ValueError(f"peak line {line_number}: invalid numeric field: {error}")
            if not contig or any(char.isspace() for char in contig):
                raise ValueError(f"peak line {line_number}: invalid contig name {contig!r}")
            if start < 0 or end <= start:
                raise ValueError(f"peak line {line_number}: invalid half-open coordinates {contig}:{start}-{end}")
            if contig not in reference_lengths:
                raise ValueError(f"peak line {line_number}: contig {contig!r} is absent from the reference")
            if end > reference_lengths[contig]:
                raise ValueError(f"peak line {line_number}: end {end} exceeds {contig} length {reference_lengths[contig]}")
            count += 1
            contigs.add(contig)
    return count, sorted(contigs)


def as_bool(value, field):
    if isinstance(value, bool):
        return value
    if str(value).lower() in {"true", "1", "yes"}:
        return True
    if str(value).lower() in {"false", "0", "no"}:
        return False
    raise ValueError(f"{field} must be boolean, got {value!r}")


def nonnegative_int(value, field):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be an integer, got {value!r}")
    if parsed < 0:
        raise ValueError(f"{field} must be >= 0, got {parsed}")
    return parsed


def identity(document, key):
    value = document.get(key)
    return "" if value is None else str(value)


def validate_identity(meta, bam_manifest, peak_manifest):
    required = ("peak_id", "record_id", "sample_id", "target", "peak_type", "caller", "caller_version")
    missing = [field for field in required if not str(meta.get(field, "")).strip()]
    if missing:
        raise ValueError("Peak QC metadata missing required field(s): " + ", ".join(missing))
    comparisons = (
        ("peak manifest id", identity(peak_manifest, "id"), str(meta["peak_id"])),
        ("peak manifest record_id", identity(peak_manifest, "record_id"), str(meta["record_id"])),
        ("peak manifest sample_id", identity(peak_manifest, "sample_id"), str(meta["sample_id"])),
        ("peak manifest target", identity(peak_manifest, "target"), str(meta["target"])),
        ("peak manifest peak_type", identity(peak_manifest, "peak_type"), str(meta["peak_type"])),
        ("peak manifest caller", identity(peak_manifest, "caller"), str(meta["caller"])),
        ("BAM manifest id", identity(bam_manifest, "id"), str(meta["record_id"])),
    )
    for label, observed, expected in comparisons:
        if observed and observed != expected:
            raise ValueError(f"{label} {observed!r} does not match expected identity {expected!r}")


def build_request(meta, bam, bai, bam_manifest_path, peaks, peak_manifest_path, reference, blacklist, spec):
    bam_manifest = load_json(bam_manifest_path, "BAM manifest")
    peak_manifest = load_json(peak_manifest_path, "peak manifest")
    validate_identity(meta, bam_manifest, peak_manifest)
    peak_type = str(meta["peak_type"]).lower()
    if peak_type not in EXPECTED_COLUMNS:
        raise ValueError(f"peak_type must be narrow or broad, got {peak_type!r}")
    lengths = fasta_lengths(reference)
    peak_count, peak_contigs = validate_peaks(peaks, peak_type, lengths)

    layout = "single" if as_bool(meta.get("single_end", False), "single_end") else "paired"
    requested_unit = str(spec.get("unit", "layout")).lower()
    if requested_unit not in {"layout", "reads", "fragments"}:
        raise ValueError(f"unit must be layout, reads, or fragments, got {requested_unit!r}")
    unit = ("reads" if layout == "single" else "fragments") if requested_unit == "layout" else requested_unit
    if layout == "single" and unit == "fragments":
        raise ValueError("single-end inputs cannot use fragment counting")

    overlap = str(spec.get("overlap_strategy", "any_base")).lower()
    if overlap != "any_base":
        raise ValueError(f"Peak QC API v1 supports overlap_strategy=any_base, got {overlap!r}")
    duplicate_handling = str(spec.get("duplicate_handling", "include")).lower()
    if duplicate_handling not in {"include", "exclude_flagged"}:
        raise ValueError("duplicate_handling must be include or exclude_flagged")
    blacklist_policy = str(spec.get("blacklist_policy", "bam_preprocessed")).lower()
    if blacklist_policy not in {"bam_preprocessed", "none"}:
        raise ValueError("blacklist_policy must be bam_preprocessed or none")

    min_mapq = nonnegative_int(spec.get("min_mapq", 0), "min_mapq")
    if min_mapq > 255:
        raise ValueError("min_mapq must be <= 255")
    include_flags = nonnegative_int(spec.get("include_flags", 0), "include_flags")
    exclude_flags = nonnegative_int(spec.get("additional_exclude_flags", 0), "additional_exclude_flags")
    filter_policy = {}
    for field, bit in FILTER_BITS.items():
        enabled = as_bool(spec.get(field, True), field)
        filter_policy[field] = enabled
        if enabled:
            exclude_flags |= bit
    if duplicate_handling == "exclude_flagged":
        exclude_flags |= 1024
    require_proper_pair = as_bool(spec.get("require_proper_pair", True), "require_proper_pair")
    if unit == "fragments" and require_proper_pair:
        include_flags |= 2
    conflicting_flags = include_flags & exclude_flags
    if conflicting_flags:
        raise ValueError(f"SAM flags cannot be both required and excluded: {conflicting_flags}")

    bam_duplicate_policy = str(meta.get("bam_duplicate_policy") or bam_manifest.get("duplicate_policy") or "unknown")
    request = {
        "schema_version": "1.0",
        "type": "peak_qc_request",
        "id": str(meta["peak_id"]),
        "peak_id": str(meta["peak_id"]),
        "record_id": str(meta["record_id"]),
        "sample_id": str(meta["sample_id"]),
        "experiment_id": str(meta.get("experiment_id", "")),
        "dataset": str(meta.get("dataset", "")),
        "target": str(meta["target"]),
        "control_id": meta.get("control_id") or None,
        "control_record_id": meta.get("control_record_id") or None,
        "biological_replicate": str(meta.get("biological_replicate", "")),
        "technical_replicate": str(meta.get("technical_replicate", "")),
        "layout": layout,
        "unit": unit,
        "peak_type": peak_type,
        "caller": str(meta["caller"]),
        "caller_version": str(meta["caller_version"]),
        "reference": str(meta.get("reference") or meta.get("genome_id") or ""),
        "filters": {
            **filter_policy,
            "min_mapq": min_mapq,
            "include_flags": include_flags,
            "exclude_flags": exclude_flags,
            "duplicate_handling": duplicate_handling,
            "bam_duplicate_policy": bam_duplicate_policy,
            "require_proper_pair": require_proper_pair,
        },
        "overlap_strategy": overlap,
        "overlap_definition": "at_least_one_reference_base",
        "overlapping_peaks": "merge_for_overlap_only",
        "blacklist_policy": blacklist_policy,
        "peak_count_validated": peak_count,
        "peak_contigs": peak_contigs,
        "inputs": {
            "bam": {"path": os.path.basename(bam), "sha256": sha256(bam)},
            "bai": {"path": os.path.basename(bai), "sha256": sha256(bai)},
            "bam_manifest": {"path": os.path.basename(bam_manifest_path), "sha256": sha256(bam_manifest_path)},
            "peaks": {"path": os.path.basename(peaks), "sha256": sha256(peaks)},
            "peak_manifest": {"path": os.path.basename(peak_manifest_path), "sha256": sha256(peak_manifest_path)},
            "reference": {"path": os.path.basename(reference), "sha256": sha256(reference)},
            "blacklist": ({"path": os.path.basename(blacklist), "sha256": sha256(blacklist)} if blacklist else {"available": False}),
        },
        "status": "valid",
    }
    return request


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--meta-base64", required=True)
    parser.add_argument("--bam", required=True)
    parser.add_argument("--bai", required=True)
    parser.add_argument("--bam-manifest", required=True)
    parser.add_argument("--peaks", required=True)
    parser.add_argument("--peak-manifest", required=True)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--blacklist")
    parser.add_argument("--spec-base64", required=True)
    parser.add_argument("--request", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    try:
        for path, label in ((args.bam, "BAM"), (args.bai, "BAI"), (args.reference, "reference")):
            require_file(path, label)
        require_file(args.peaks, "peak file", allow_empty=True)
        if args.blacklist:
            require_file(args.blacklist, "blacklist")
        meta = json.loads(base64.b64decode(args.meta_base64).decode("utf-8"))
        spec = json.loads(base64.b64decode(args.spec_base64).decode("utf-8"))
        request = build_request(
            meta, args.bam, args.bai, args.bam_manifest, args.peaks,
            args.peak_manifest, args.reference, args.blacklist, spec,
        )
        for path in (args.request, args.report):
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(request, handle, indent=2, sort_keys=True)
                handle.write("\n")
        print(f"validated Peak QC association for {request['peak_id']} ({request['unit']})")
    except (ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
