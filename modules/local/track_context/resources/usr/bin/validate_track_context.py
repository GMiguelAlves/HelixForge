#!/usr/bin/env python3
import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import sys


DEFAULTS = {
    "provider": "deeptools_bamcoverage_v1", "track_format": "bigwig",
    "bin_size": 10, "normalization": "CPM", "effective_genome_size": None,
    "scale_factor": 1.0, "extend_reads": False, "fragment_mode": "reads",
    "strand": "unstranded", "additional_filters": "none",
}


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_id(value, label):
    value = str(value or "")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", value):
        raise ValueError(f"invalid or empty {label}: {value!r}")
    return value


def load_json(path, label):
    with open(path, encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{label} must contain a JSON object")
    return value


def validate_spec(raw):
    unknown = set(raw or {}) - set(DEFAULTS)
    if unknown:
        raise ValueError("unsupported track parameter(s): " + ",".join(sorted(unknown)))
    spec = dict(DEFAULTS); spec.update(raw or {})
    if spec["provider"] != "deeptools_bamcoverage_v1":
        raise ValueError(f"unsupported track provider {spec['provider']!r}")
    if spec["track_format"] != "bigwig":
        raise ValueError("v1 supports only track_format=bigwig")
    if isinstance(spec["bin_size"], bool) or not isinstance(spec["bin_size"], int) or spec["bin_size"] < 1:
        raise ValueError("bin_size must be a positive integer")
    if spec["normalization"] not in {"CPM", "RPGC"}:
        raise ValueError("normalization must be CPM or RPGC")
    effective = spec["effective_genome_size"]
    if spec["normalization"] == "RPGC" and (isinstance(effective, bool) or not isinstance(effective, int) or effective < 1):
        raise ValueError("RPGC requires a positive effective_genome_size")
    if spec["normalization"] == "CPM" and effective is not None:
        raise ValueError("effective_genome_size is applicable only to RPGC")
    if isinstance(spec["scale_factor"], bool) or float(spec["scale_factor"]) != 1.0:
        raise ValueError("v1 supports scale_factor=1.0 only")
    spec["scale_factor"] = 1.0
    if spec["extend_reads"] is not False:
        raise ValueError("v1 supports extend_reads=false only")
    if spec["fragment_mode"] != "reads":
        raise ValueError("v1 supports fragment_mode=reads only")
    if spec["strand"] != "unstranded":
        raise ValueError("v1 supports strand=unstranded only")
    if spec["additional_filters"] != "none":
        raise ValueError("track provider cannot apply additional filters")
    return spec


def reference_contigs(path):
    result, name, length = {}, None, 0
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if line.startswith(">"):
                if name is not None:
                    result[name] = length
                name = line[1:].strip().split()[0]; length = 0
                if not name or name in result:
                    raise ValueError(f"empty or duplicate reference contig {name!r}")
            else:
                length += len(line.strip())
    if name is not None:
        result[name] = length
    if not result or any(value < 1 for value in result.values()):
        raise ValueError("reference contains no valid contigs")
    return result


def bam_contigs(path):
    result = subprocess.run(["samtools", "view", "-H", path], capture_output=True, text=True, check=False)
    if result.returncode:
        raise ValueError(f"cannot read BAM header {path}: {result.stderr.strip()}")
    contigs = {}
    for line in result.stdout.splitlines():
        if not line.startswith("@SQ\t"):
            continue
        fields = dict(field.split(":", 1) for field in line.split("\t")[1:] if ":" in field)
        if "SN" in fields and "LN" in fields:
            if fields["SN"] in contigs:
                raise ValueError(f"duplicate BAM contig {fields['SN']!r}")
            contigs[fields["SN"]] = int(fields["LN"])
    if not contigs:
        raise ValueError(f"BAM has no @SQ records: {path}")
    return contigs


def index_by_basename(paths, label):
    result = {}
    for path in paths:
        name = os.path.basename(path)
        if name in result:
            raise ValueError(f"duplicate staged {label} basename {name!r}")
        result[name] = path
    return result


def find_artifact(index, declared, label):
    name = os.path.basename(str(declared or ""))
    if not name or name not in index:
        raise ValueError(f"{label} artifact {name!r} is absent from staged inputs")
    return index[name]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--meta-base64", required=True)
    parser.add_argument("--bam", action="append", required=True)
    parser.add_argument("--bai", action="append", required=True)
    parser.add_argument("--bam-manifest", action="append", required=True)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--reference-manifest", required=True)
    parser.add_argument("--spec-base64", required=True)
    parser.add_argument("--request", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    try:
        meta = json.loads(base64.b64decode(args.meta_base64).decode("utf-8"))
        spec = validate_spec(json.loads(base64.b64decode(args.spec_base64).decode("utf-8")))
        request_id = safe_id(meta.get("id"), "track id")
        role = meta.get("track_role")
        if role not in {"individual", "aggregate"}:
            raise ValueError("track_role must be individual or aggregate")
        record_ids = [safe_id(value, "record_id") for value in meta.get("record_ids", [])]
        sample_ids = [safe_id(value, "sample_id") for value in meta.get("sample_ids", [])]
        if not record_ids or len(record_ids) != len(set(record_ids)) or len(record_ids) != len(sample_ids):
            raise ValueError("record_ids must be non-empty/unique and align with sample_ids in metadata")
        if role == "individual" and len(record_ids) != 1:
            raise ValueError("individual track requires exactly one record_id")
        if role == "aggregate" and len(record_ids) < 1:
            raise ValueError("aggregate track requires at least one source record")
        bam_index = index_by_basename(args.bam, "BAM")
        bai_index = index_by_basename(args.bai, "BAI")
        documents = {}
        for path in args.bam_manifest:
            document = load_json(path, "final BAM manifest")
            if document.get("type") != "bam_final":
                raise ValueError(f"{path}: expected type=bam_final")
            identifier = safe_id(document.get("id"), "final BAM manifest id")
            if identifier in documents:
                raise ValueError(f"duplicate final BAM manifest id {identifier!r}")
            documents[identifier] = (document, path)
        if set(documents) != set(record_ids):
            raise ValueError("metadata record_ids and final BAM manifests disagree")
        ref_doc = load_json(args.reference_manifest, "reference manifest")
        if ref_doc.get("type") not in {"reference_bundle", "reference", "alignment_reference"}:
            raise ValueError(f"unsupported reference manifest type {ref_doc.get('type')!r}")
        genome_id = safe_id(meta.get("genome_id"), "genome_id")
        build = safe_id(meta.get("build"), "build")
        ref_genome = safe_id(ref_doc.get("genome_id") or ref_doc.get("build"), "reference genome_id")
        ref_build = safe_id(ref_doc.get("build") or ref_genome, "reference build")
        if (genome_id, build) != (ref_genome, ref_build):
            raise ValueError("track metadata and reference manifest disagree on genome/build")
        reference_sha = sha256(args.reference)
        ref_artifacts = ref_doc.get("artifacts", {})
        ref_artifact = next((ref_artifacts.get(key) for key in ("reference", "fasta", "genome") if isinstance(ref_artifacts.get(key), dict)), None)
        if ref_artifact and ref_artifact.get("sha256") and ref_artifact["sha256"] != reference_sha:
            raise ValueError("reference checksum does not match reference manifest")
        expected_contigs = reference_contigs(args.reference)
        expected_samples = dict(zip(record_ids, sample_ids))
        sources = []
        for identifier in sorted(documents):
            document, manifest_path = documents[identifier]
            if document.get("sample_id") != expected_samples[identifier]:
                raise ValueError(f"{identifier}: metadata and final BAM manifest disagree on sample_id")
            bam = find_artifact(bam_index, document.get("artifact"), "BAM")
            bai = find_artifact(bai_index, document.get("index"), "BAI")
            if document.get("sha256") and sha256(bam) != document["sha256"]:
                raise ValueError(f"{identifier}: BAM checksum mismatch")
            if document.get("index_sha256") and sha256(bai) != document["index_sha256"]:
                raise ValueError(f"{identifier}: BAI checksum mismatch")
            if document.get("reference_sha256") and document["reference_sha256"] != reference_sha:
                raise ValueError(f"{identifier}: BAM/reference checksum mismatch")
            quickcheck = subprocess.run(["samtools", "quickcheck", "-v", bam], capture_output=True, text=True, check=False)
            if quickcheck.returncode:
                raise ValueError(f"{identifier}: samtools quickcheck failed: {quickcheck.stderr.strip()}")
            if bam_contigs(bam) != expected_contigs:
                raise ValueError(f"{identifier}: BAM and reference contigs/lengths are incompatible")
            sources.append({
                "record_id": identifier, "sample_id": expected_samples[identifier],
                "bam": os.path.basename(bam), "bai": os.path.basename(bai),
                "bam_sha256": sha256(bam), "bai_sha256": sha256(bai),
                "manifest": os.path.basename(manifest_path), "manifest_sha256": sha256(manifest_path),
                "duplicate_policy": document.get("duplicate_policy"),
                "selection": document.get("selection"), "blacklist_policy": document.get("blacklist_policy"),
            })
        request = {
            "schema_version": "1.0", "type": "track_request", "id": request_id,
            "track_role": role, "record_id": record_ids[0] if role == "individual" else None,
            "record_ids": record_ids, "sample_ids": sample_ids,
            "dataset": meta.get("dataset"), "condition": meta.get("condition"),
            "target": meta.get("target"), "is_control": meta.get("is_control") if role == "individual" else False,
            "biological_replicates": meta.get("biological_replicates", []),
            "technical_replicates": meta.get("technical_replicates", []),
            "genome_id": genome_id, "build": build,
            "provider": spec.pop("provider"), "provider_version": "1.0.0",
            "parameters": spec, "sources": sources,
            "reference": {"path": os.path.basename(args.reference), "sha256": reference_sha},
            "reference_manifest": {"path": os.path.basename(args.reference_manifest), "sha256": sha256(args.reference_manifest)},
            "status": "valid",
        }
        with open(args.request, "w", encoding="utf-8") as handle:
            json.dump(request, handle, indent=2, sort_keys=True); handle.write("\n")
        with open(args.report, "w", encoding="utf-8") as handle:
            json.dump({"schema_version": "1.0", "id": request_id, "checks": {"identity": "pass", "bam_index": "pass", "checksums": "pass", "reference": "pass", "contigs": "pass", "parameters": "pass"}, "status": "valid"}, handle, indent=2, sort_keys=True); handle.write("\n")
    except (ValueError, KeyError, json.JSONDecodeError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr); return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
