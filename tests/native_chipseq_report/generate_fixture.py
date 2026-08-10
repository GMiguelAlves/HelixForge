#!/usr/bin/env python3
import argparse
import hashlib
import json
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", required=True)
    args = parser.parse_args()
    root = Path(args.outdir); root.mkdir(parents=True, exist_ok=True)
    project = {"project_id": "fixture_project", "dataset": "fixture_dataset", "genome_id": "fixture_v1", "build": "fixture_v1"}

    consensus_summary = root / "consensus_summary.json"
    write(consensus_summary, {"schema_version": "1.0", "type": "consensus_idr_summary", "rows": [{"group_id": "treated.H3K27ac", "strategy": "union", "replicates": 2, "regions": 125, "status": "complete"}], "status": "complete"})
    track_table = root / "tracks.tsv"
    track_table.write_text("track_id\ttrack_role\tsample_ids\tnormalization\tbin_size\tstatus\nchip_rep1.bigwig\tindividual\tchip_rep1\tCPM\t10\tcomplete\n", encoding="utf-8")
    db_summary = root / "differential_binding_summary.tsv"
    db_summary.write_text("analysis_id\tcontrast\tsamples\tpeaks\tsignificant\tstatus\nH3K27ac\ttreated_vs_control\t4\t125\t12\tcomplete\n", encoding="utf-8")
    annotation_stats = root / "annotation_statistics.tsv"
    annotation_stats.write_text("id\tannotated_peaks\tintergenic_peaks\tgenes\nconsensus.annotation\t125\t20\t80\n", encoding="utf-8")

    manifests = {
        "metadata": {"schema_version": "1.0", "type": "chipseq_metadata", "id": "fixture.metadata", "dataset": project["dataset"], "genome_id": project["genome_id"], "build": project["build"], "rows": [{"record_id": "chip_rep1", "sample_id": "chip_rep1", "dataset": project["dataset"], "condition": "treated", "target": "H3K27ac", "biological_replicate": "1", "technical_replicate": "1", "is_control": False}], "status": "complete"},
        "reference": {"schema_version": "1.0", "type": "reference_bundle", "id": "fixture.reference", "genome_id": project["genome_id"], "build": project["build"], "status": "complete"},
        "bam": {"schema_version": "1.0", "type": "bam_final", "id": "chip_rep1", "record_id": "chip_rep1", "sample_id": "chip_rep1", "dataset": project["dataset"], "genome_id": project["genome_id"], "build": project["build"], "duplicate_policy": "none", "blacklist_policy": "fragment", "selection": {"min_mapq": 30, "include_flags": 0, "exclude_flags": 2308}, "metrics": {"total_reads": 1000, "mapped_reads": 900, "properly_paired": 850, "duplicates": None}, "status": "complete"},
        "peak": {"schema_version": "1.0", "type": "peak_calling", "id": "chip_rep1.H3K27ac.narrow.macs3", "record_id": "chip_rep1", "sample_id": "chip_rep1", "dataset": project["dataset"], "condition": "treated", "target": "H3K27ac", "biological_replicate": "1", "technical_replicate": "1", "caller": "macs3", "caller_version": "3.0.4", "peak_type": "narrow", "metrics": {"total_peaks": 100}, "status": "complete"},
        "peak_qc": {"schema_version": "1.0", "type": "peak_qc", "id": "fixture.peak_qc", "rows": [{"record_id": "chip_rep1", "sample_id": "chip_rep1", "peak_id": "chip_rep1.H3K27ac.narrow.macs3", "frip": 0.21, "total_peaks": 100}], "status": "complete"},
        "consensus": {"schema_version": "1.0", "type": "consensus_idr", "id": "fixture.consensus", "strategy": "union", "artifacts": {"summary_json": {"path": "consensus_summary.json", "sha256": digest(consensus_summary)}}, "status": "complete"},
        "idr": {"schema_version": "1.0", "type": "idr", "id": "fixture.idr", "strategy": "idr", "artifacts": {"consolidated_peaks": {"available": False}}, "status": "not_implemented"},
        "db": {"schema_version": "1.0", "type": "differential_binding", "id": "fixture.db", "design": "~ condition", "contrasts": 1, "artifacts": {"summary": {"path": "differential_binding_summary.tsv", "sha256": digest(db_summary)}}, "status": "complete"},
        "annotation": {"schema_version": "1.0", "type": "peak_annotation_aggregate", "id": "fixture.annotation", "records": 1, "artifacts": {"statistics": {"path": "annotation_statistics.tsv", "sha256": digest(annotation_stats)}}, "status": "complete"},
        "tracks": {"schema_version": "1.0", "type": "track_aggregate", "id": "fixture.tracks", "tracks": 1, "artifacts": {"track_table": {"path": "tracks.tsv", "sha256": digest(track_table)}}, "status": "complete"},
    }
    manifest_paths = {}
    for name, document in manifests.items():
        path = root / f"{name}.manifest.json"; write(path, document); manifest_paths[name] = path

    entries = []
    role_names = {"db": "differential_binding", "consensus": "consensus_idr", "idr": "consensus_idr"}
    artifact_names = {"consensus": [consensus_summary.name], "db": [db_summary.name], "annotation": [annotation_stats.name], "tracks": [track_table.name]}
    for name in ("metadata", "reference", "bam", "peak", "peak_qc", "consensus", "idr", "db", "annotation", "tracks"):
        entries.append({"component": role_names.get(name, name), "manifest": manifest_paths[name].name, "artifacts": artifact_names.get(name, [])})
    write(root / "report_input.json", {"schema_version": "1.0", "type": "chipseq_report_input", "project": project, "required_components": ["bam"], "components": entries})


if __name__ == "__main__":
    main()
