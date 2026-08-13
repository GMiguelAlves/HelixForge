#!/usr/bin/env python3
"""Build manifest-backed inputs between supported top-level ChIP-seq modes."""

import argparse
import csv
import hashlib
import json
import shlex
from pathlib import Path


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exactly(paths, label, count=None):
    values = sorted(set(path.resolve() for path in paths))
    if not values or (count is not None and len(values) != count):
        raise ValueError(f"expected {count or 'at least one'} {label}, found {len(values)}")
    return values


def read_metadata(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def build_metadata_manifest(case_root, rows):
    path = case_root / "inputs/metadata_manifest.json"
    document = {
        "schema_version": "1.0",
        "type": "chipseq_metadata",
        "id": "synthetic.metadata",
        "dataset": "synthetic_chipseq_validation",
        "genome_id": "synthetic_v1",
        "build": "synthetic_v1",
        "rows": rows,
        "status": "complete",
    }
    dump(path, document)
    return path


def annotation(case_root):
    results = case_root / "results"
    manifests = exactly(results.glob("chipseq/consensus/*/*.consensus_result/manifest.json"), "consensus manifests", 2)
    selected = None
    for manifest in manifests:
        document = load(manifest)
        if document.get("condition") == "treated":
            selected = (manifest, document)
            break
    if selected is None:
        raise ValueError("no treated consensus manifest was produced")
    manifest, document = selected
    peaks = manifest.parent / document["artifacts"]["consolidated_bed"]["path"]
    if sha256(peaks) != document["artifacts"]["consolidated_bed"]["sha256"]:
        raise ValueError("consensus BED checksum mismatch")
    env = case_root / "inputs/annotation.env"
    values = {
        "ANNOTATION_PEAKS": peaks,
        "ANNOTATION_PEAK_MANIFEST": manifest,
        "ANNOTATION_REFERENCE": case_root / "fixture/reference/genome.fa",
        "ANNOTATION_REFERENCE_MANIFEST": case_root / "fixture/reference/reference_manifest.json",
        "ANNOTATION_GTF": case_root / "fixture/reference/annotation.gtf",
    }
    env.parent.mkdir(parents=True, exist_ok=True)
    env.write_text("".join(f"{key}={shlex.quote(str(value.resolve()))}\n" for key, value in values.items()), encoding="utf-8")
    print(env)


def tracks(case_root):
    results = case_root / "results"
    metadata_path = exactly(results.glob("pipeline_info/native_chipseq/metadata/validated_metadata.tsv"), "validated metadata", 1)[0]
    rows = read_metadata(metadata_path)
    manifests = exactly(results.glob("pipeline_info/native_chipseq/bam_final/*.manifest.json"), "final BAM manifests", len(rows))
    by_id = {load(path)["id"]: (path, load(path)) for path in manifests}
    records = []
    for row in rows:
        record_id = row["record_id"]
        manifest_path, document = by_id[record_id]
        bam = results / "060-filtering" / record_id / document["artifact"]
        bai = results / "060-filtering" / record_id / document["index"]
        for path in (bam, bai):
            if not path.is_file():
                raise ValueError(f"missing final BAM artifact: {path}")
        records.append(
            {
                "record_id": record_id,
                "sample_id": row["sample_id"],
                "dataset": row["dataset"],
                "condition": row["condition"],
                "target": row["target"],
                "biological_replicate": row["biological_replicate"],
                "technical_replicate": row["technical_replicate"],
                "is_control": row["is_control"].lower() == "true",
                "bam": str(bam.resolve()),
                "bai": str(bai.resolve()),
                "bam_manifest": str(manifest_path.resolve()),
            }
        )
    inventory = {
        "schema_version": "1.0",
        "type": "track_generation_input",
        "reference": {
            "fasta": str((case_root / "fixture/reference/genome.fa").resolve()),
            "manifest": str((case_root / "fixture/reference/reference_manifest.json").resolve()),
            "genome_id": "synthetic_v1",
            "build": "synthetic_v1",
        },
        "records": records,
    }
    path = case_root / "inputs/tracks_input.json"
    dump(path, inventory)
    print(path)


def declared_artifact(manifest_path, keys):
    document = load(manifest_path)
    for key in keys:
        item = document.get("artifacts", {}).get(key)
        if isinstance(item, dict) and item.get("path") and item.get("sha256"):
            path = manifest_path.parent / item["path"]
            if not path.is_file():
                candidates = list(manifest_path.parent.rglob(Path(item["path"]).name))
                if len(candidates) == 1:
                    path = candidates[0]
            if path.is_file() and sha256(path) == item["sha256"]:
                return path
    return None


def report(case_root):
    results = case_root / "results"
    metadata_rows = read_metadata(exactly(results.glob("pipeline_info/native_chipseq/metadata/validated_metadata.tsv"), "validated metadata", 1)[0])
    metadata_manifest = build_metadata_manifest(case_root, metadata_rows)
    reference_manifest = case_root / "fixture/reference/reference_manifest.json"
    bam_manifests = exactly(results.glob("pipeline_info/native_chipseq/bam_final/*.manifest.json"), "BAM manifests", 5)
    peak_manifests = exactly(results.glob("080-peak-calling/*.peak_calling/manifest.json"), "peak manifests", 4)
    peak_qc_manifest = exactly(results.glob("pipeline_info/native_chipseq/peak_qc/aggregate/peak_qc_manifest.json"), "peak-QC manifest", 1)[0]
    consensus_manifests = exactly(results.glob("chipseq/consensus/*/*.consensus_result/manifest.json"), "consensus manifests", 2)
    db_manifest = exactly(results.glob("120-differential-binding/manifest.json"), "DB manifest", 1)[0]
    annotation_manifest = exactly(results.glob("chipseq/peak_annotation/peak_annotation_aggregate/manifest.json"), "annotation manifest", 1)[0]
    tracks_manifest = exactly(results.glob("chipseq/tracks/track_aggregate/manifest.json"), "track manifest", 1)[0]

    entries = [
        {"component": "metadata", "manifest": str(metadata_manifest.resolve()), "artifacts": []},
        {"component": "reference", "manifest": str(reference_manifest.resolve()), "artifacts": []},
    ]
    entries.extend({"component": "bam", "manifest": str(path), "artifacts": []} for path in bam_manifests)
    entries.extend({"component": "peak", "manifest": str(path), "artifacts": []} for path in peak_manifests)

    qc_artifact = results / "chipseq/peak_qc/peak_qc_summary.json"
    entries.append({"component": "peak_qc", "manifest": str(peak_qc_manifest), "artifacts": [str(qc_artifact.resolve())]})
    entries.extend({"component": "consensus_idr", "manifest": str(path), "artifacts": []} for path in consensus_manifests)

    db_artifact = declared_artifact(db_manifest, ("summary",))
    annotation_artifact = declared_artifact(annotation_manifest, ("statistics",))
    tracks_artifact = declared_artifact(tracks_manifest, ("track_table", "tracks"))
    entries.append({"component": "differential_binding", "manifest": str(db_manifest), "artifacts": [str(db_artifact)] if db_artifact else []})
    entries.append({"component": "annotation", "manifest": str(annotation_manifest), "artifacts": [str(annotation_artifact)] if annotation_artifact else []})
    entries.append({"component": "tracks", "manifest": str(tracks_manifest), "artifacts": [str(tracks_artifact)] if tracks_artifact else []})

    inventory = {
        "schema_version": "1.0",
        "type": "chipseq_report_input",
        "project": {
            "project_id": "synthetic_chipseq_validation",
            "dataset": "synthetic_chipseq_validation",
            "genome_id": "synthetic_v1",
            "build": "synthetic_v1",
        },
        "required_components": [
            "metadata", "reference", "bam", "peak", "peak_qc", "consensus_idr",
            "differential_binding", "annotation", "tracks",
        ],
        "components": entries,
    }
    path = case_root / "inputs/report_input.json"
    dump(path, inventory)
    print(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("annotation", "tracks", "report"))
    parser.add_argument("--case-root", required=True, type=Path)
    args = parser.parse_args()
    globals()[args.stage](args.case_root.resolve())


if __name__ == "__main__":
    main()
