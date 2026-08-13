#!/usr/bin/env python3
"""Validate the reduced top-level ChIP-seq Slurm execution semantically."""

import argparse
import csv
import hashlib
import json
import subprocess
from pathlib import Path


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def rows(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def require(path):
    if not path.is_file() or path.stat().st_size == 0:
        raise AssertionError(f"missing or empty artifact: {path}")
    return path


def find_exact(root, pattern, count):
    found = sorted(root.glob(pattern))
    if len(found) != count:
        raise AssertionError(f"{pattern}: expected {count}, found {len(found)}")
    return found


def trace_metrics(path):
    entries = rows(require(path))
    if not entries:
        raise AssertionError(f"empty trace: {path}")
    failed = [row for row in entries if row.get("status") not in {"COMPLETED", "CACHED"}]
    if failed:
        raise AssertionError(f"failed trace entries in {path}: {failed[:3]}")
    duration_ms = 0
    for row in entries:
        raw = row.get("realtime") or row.get("duration") or "0"
        if raw.isdigit():
            duration_ms += int(raw)
    return len(entries), duration_ms


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    case_root = args.case_root.resolve()
    result = case_root / "results"
    checks = {}

    metadata = rows(require(result / "pipeline_info/native_chipseq/metadata/validated_metadata.tsv"))
    assert len(metadata) == 5
    assert sum(row["is_control"].lower() == "true" for row in metadata) == 1
    checks["metadata"] = {"records": 5, "controls": 1, "status": "pass"}

    require(result / "030-qc-fastq/multiqc/raw_fastq_multiqc.html")
    fastqc_zips = find_exact(result, "030-qc-fastq/raw/*/*_fastqc.zip", 10)
    checks["qc"] = {"fastqc_archives": len(fastqc_zips), "multiqc": True, "status": "pass"}

    bam_manifests = find_exact(result, "pipeline_info/native_chipseq/bam_final/*.manifest.json", 5)
    bam_reads = {}
    for manifest in bam_manifests:
        document = load(manifest)
        bam = require(result / "060-filtering" / document["id"] / document["artifact"])
        require(result / "060-filtering" / document["id"] / document["index"])
        subprocess.run(["samtools", "quickcheck", "-v", str(bam)], check=True)
        observed = int(subprocess.check_output(["samtools", "view", "-c", str(bam)], text=True).strip())
        assert observed > 0
        bam_reads[document["id"]] = observed
    checks["bam_processing"] = {"records": 5, "reads": bam_reads, "status": "pass"}

    peak_manifests = find_exact(result, "080-peak-calling/*.peak_calling/manifest.json", 4)
    peak_counts = {}
    for manifest in peak_manifests:
        document = load(manifest)
        assert document["status"] in {"complete", "complete_empty"}
        assert document["peak_type"] == "narrow"
        assert document["caller"] == "macs3"
        assert document["control_record_id"] == "input_rep1"
        assert document["metrics"]["total_peaks"] > 0
        peak_counts[document["record_id"]] = document["metrics"]["total_peaks"]
    checks["peak_calling"] = {"records": 4, "peak_counts": peak_counts, "status": "pass"}

    qc_rows = rows(require(result / "chipseq/peak_qc/peak_qc_summary.tsv"))
    assert len(qc_rows) == 4
    for row in qc_rows:
        assert 0.0 <= float(row["frip"]) <= 1.0
        assert int(row["peak_count"]) > 0
    checks["peak_qc"] = {"records": 4, "frip": [float(row["frip"]) for row in qc_rows], "status": "pass"}

    consensus_manifests = find_exact(result, "chipseq/consensus/*/*.consensus_result/manifest.json", 2)
    consensus = {}
    for manifest in consensus_manifests:
        document = load(manifest)
        assert document["strategy"] == "union"
        assert document["status"] == "complete"
        assert len(document["replicates"]) == 2
        assert document["statistics"]["consolidated_peaks"] > 0
        consensus[document["condition"]] = document["statistics"]["consolidated_peaks"]
    assert set(consensus) == {"control", "treated"}
    checks["consensus"] = {"groups": consensus, "status": "pass"}

    db_root = result / "120-differential-binding/differential_binding_results"
    db_manifest = load(require(db_root / "manifest.json"))
    assert db_manifest["status"] == "complete"
    assert db_manifest["contrasts"] == 1
    db_rows = rows(require(db_root / "differential_binding_results.tsv"))
    assert db_rows and {row["contrast"] for row in db_rows} == {"treated_vs_control"}
    checks["differential_binding"] = {"rows": len(db_rows), "contrasts": 1, "status": "pass"}

    annotation_root = result / "chipseq/peak_annotation/peak_annotation_aggregate"
    annotation_manifest = load(require(annotation_root / "manifest.json"))
    annotation_rows = rows(require(annotation_root / "annotated_peaks.tsv"))
    assert annotation_manifest["status"] == "complete" and annotation_rows
    checks["annotation"] = {"peaks": len(annotation_rows), "status": "pass"}

    tracks_root = result / "chipseq/tracks/track_aggregate"
    track_manifest = load(require(tracks_root / "manifest.json"))
    track_rows = rows(require(tracks_root / "tracks.tsv"))
    assert track_manifest["status"] == "complete"
    assert len(track_rows) == 7
    assert sum(row["track_role"] == "aggregate" for row in track_rows) == 2
    for row in track_rows:
        require(tracks_root / row["track"])
    checks["tracks"] = {"tracks": 7, "aggregate_tracks": 2, "status": "pass"}

    report_root = result / "chipseq/report/report_result"
    report_manifest = load(require(report_root / "manifest.json"))
    report_html = require(report_root / "chipseq_report.html")
    report_text = report_html.read_text(encoding="utf-8")
    for section in ("Peak QC", "Differential binding", "Annotation", "Tracks"):
        assert section in report_text
    assert report_manifest["status"] in {"complete", "available"}
    checks["report"] = {"bytes": report_html.stat().st_size, "status": "pass"}

    stage_metrics = {}
    for stage in ("differential_binding", "annotation", "tracks", "report"):
        count, duration = trace_metrics(case_root / "traces" / f"{stage}.tsv")
        stage_metrics[stage] = {"processes": count, "reported_duration_ms": duration}
    checks["execution"] = {"stages": stage_metrics, "status": "pass"}

    input_checksums = rows(require(case_root / "input_checksums.tsv"))
    for row in input_checksums:
        path = case_root / "fixture/fastq" / row["artifact"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"]
    checks["input_checksums"] = {"files": len(input_checksums), "status": "pass"}

    output = {
        "schema_version": "1.0",
        "type": "chipseq_top_level_validation",
        "dataset": "synthetic_chipseq_validation",
        "nextflow_version": "25.10.7",
        "checks": checks,
        "status": "pass",
    }
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (case_root / "benchmark.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(("stage", "processes", "reported_duration_ms"))
        for stage, values in stage_metrics.items():
            writer.writerow((stage, values["processes"], values["reported_duration_ms"]))
    print(json.dumps({"status": "pass", "checks": len(checks), "stages": stage_metrics}, sort_keys=True))


if __name__ == "__main__":
    main()
