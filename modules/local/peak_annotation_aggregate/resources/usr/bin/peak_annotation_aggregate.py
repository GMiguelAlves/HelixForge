#!/usr/bin/env python3
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys
import time


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_documents(paths, expected_type):
    result = {}
    for path in paths:
        with open(path, encoding="utf-8") as handle:
            doc = json.load(handle)
        if doc.get("type") != expected_type:
            raise ValueError(f"{path}: expected type {expected_type}")
        identifier = doc.get("id")
        if not identifier or identifier in result:
            raise ValueError(f"empty or duplicate annotation id {identifier!r}")
        result[identifier] = (doc, path)
    return result


def index_directories(paths):
    result = {}
    for path in paths:
        manifest = Path(path) / "manifest.json"
        with manifest.open(encoding="utf-8") as handle:
            identifier = json.load(handle).get("id")
        if not identifier or identifier in result:
            raise ValueError(f"empty or duplicate annotation directory id {identifier!r}")
        result[identifier] = Path(path)
    return result


def read_rows(path):
    with open(path, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_rows(path, columns, rows):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", lineterminator="\n", extrasaction="ignore")
        writer.writeheader(); writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--annotation-dir", action="append", required=True)
    parser.add_argument("--annotation-manifest", action="append", required=True)
    parser.add_argument("--statistics-json", action="append", required=True)
    parser.add_argument("--statistics-manifest", action="append", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--execution", required=True)
    parser.add_argument("--versions", required=True)
    parser.add_argument("--cpus", type=int, required=True)
    parser.add_argument("--memory-bytes", type=int, required=True)
    parser.add_argument("--task-time", required=True)
    args = parser.parse_args()
    started = int(time.time())
    try:
        docs = load_documents(args.annotation_manifest, "peak_annotation")
        stats_docs = load_documents(args.statistics_manifest, "peak_annotation_statistics")
        directories = index_directories(args.annotation_dir)
        stats_values = {}
        for path in args.statistics_json:
            with open(path, encoding="utf-8") as handle:
                value = json.load(handle)
            identifier = value.get("id")
            if not identifier or identifier in stats_values:
                raise ValueError(f"empty or duplicate statistics id {identifier!r}")
            stats_values[identifier] = value
        identities = set(docs)
        if identities != set(stats_docs) or identities != set(directories) or identities != set(stats_values):
            raise ValueError("annotation directories/manifests/statistics disagree on IDs")
        annotated_rows, association_rows, summary_rows = [], [], []
        for identifier in sorted(identities):
            doc = docs[identifier][0]
            for row in read_rows(directories[identifier] / "annotated_peaks.tsv"):
                annotated_rows.append({"annotation_id": identifier, **row})
            for row in read_rows(directories[identifier] / "peak_gene_associations.tsv"):
                association_rows.append({"annotation_id": identifier, **row})
            value = stats_values[identifier]
            summary_rows.append({
                "annotation_id": identifier, "source_id": doc["source_id"],
                "record_id": doc.get("record_id") or "", "total_peaks": value["total_peaks"],
                "annotated_peaks": value["annotated_peaks"], "unassociated_peaks": value["unassociated_peaks"],
                "unique_genes": value["unique_genes"], "mean_genes_per_peak": value["mean_genes_per_peak"],
                "status": value["status"],
            })
        output = Path(args.output_dir); output.mkdir(parents=True, exist_ok=True)
        annotated_columns = ("annotation_id", "peak_id", "chrom", "start", "end", "category", "gene_ids", "gene_count", "distance_to_tss", "record_id", "source_id", "included")
        association_columns = ("annotation_id", "peak_id", "gene_id", "category", "distance_to_tss", "record_id", "source_id")
        summary_columns = ("annotation_id", "source_id", "record_id", "total_peaks", "annotated_peaks", "unassociated_peaks", "unique_genes", "mean_genes_per_peak", "status")
        write_rows(output / "annotated_peaks.tsv", annotated_columns, annotated_rows)
        write_rows(output / "peak_gene_associations.tsv", association_columns, association_rows)
        write_rows(output / "statistics.tsv", summary_columns, summary_rows)
        ended = int(time.time())
        execution = {"schema_version": "1.0", "id": "chipseq.peak_annotation.aggregate", "process": "PEAK_ANNOTATION_AGGREGATE", "cpus": args.cpus, "memory_bytes": args.memory_bytes, "time": args.task_time, "started_epoch": started, "ended_epoch": ended, "elapsed_seconds": ended - started}
        with open(args.execution, "w", encoding="utf-8") as handle:
            json.dump(execution, handle, indent=2, sort_keys=True); handle.write("\n")
        with open(args.versions, "w", encoding="utf-8") as handle:
            handle.write(f'"PEAK_ANNOTATION_AGGREGATE":\n    python: "{sys.version.split()[0]}"\n')
        manifest = {"schema_version": "1.0", "type": "peak_annotation_aggregate", "records": len(summary_rows), "annotation_manifests": [{"id": identifier, "sha256": sha256(path), "status": doc["status"]} for identifier, (doc, path) in sorted(docs.items())], "artifacts": {"annotated_peaks": {"path": "annotated_peaks.tsv", "sha256": sha256(output / "annotated_peaks.tsv")}, "peak_gene_associations": {"path": "peak_gene_associations.tsv", "sha256": sha256(output / "peak_gene_associations.tsv")}, "statistics": {"path": "statistics.tsv", "sha256": sha256(output / "statistics.tsv")}}, "execution": execution, "status": "complete" if summary_rows else "complete_empty"}
        manifest["id"] = "chipseq.peak_annotation.aggregate"
        with open(args.manifest, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2, sort_keys=True); handle.write("\n")
        with open(output / "manifest.json", "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2, sort_keys=True); handle.write("\n")
    except (ValueError, KeyError, json.JSONDecodeError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr); return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
