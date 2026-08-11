#!/usr/bin/env python3
import argparse
from collections import Counter
import csv
import hashlib
import json
import statistics
from pathlib import Path
import sys
import time


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_tsv(path):
    with open(path, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def distribution(values):
    if not values:
        return {"available": False, "count": 0, "min": None, "max": None, "mean": None, "median": None}
    return {"available": True, "count": len(values), "min": min(values), "max": max(values), "mean": statistics.fmean(values), "median": statistics.median(values)}


def write_rows(path, columns, rows):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--annotation-dir", required=True)
    parser.add_argument("--annotation-manifest", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-tsv", required=True)
    parser.add_argument("--reports", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--execution", required=True)
    parser.add_argument("--versions", required=True)
    parser.add_argument("--cpus", type=int, required=True)
    parser.add_argument("--memory-bytes", type=int, required=True)
    parser.add_argument("--task-time", required=True)
    args = parser.parse_args()
    started = int(time.time())
    try:
        with open(args.annotation_manifest, encoding="utf-8") as handle:
            source = json.load(handle)
        if source.get("type") != "peak_annotation":
            raise ValueError("statistics requires a peak_annotation manifest")
        root = Path(args.annotation_dir)
        annotated = read_tsv(root / "annotated_peaks.tsv")
        associations = read_tsv(root / "peak_gene_associations.tsv")
        category_counts = Counter(row["category"] for row in annotated)
        chromosome_counts = Counter(row["chrom"] for row in annotated)
        genes = {row["gene_id"] for row in associations if row.get("gene_id")}
        gene_counts = [int(row.get("gene_count") or 0) for row in annotated]
        annotated_count = sum(value > 0 for value in gene_counts)
        distances = [float(row["distance_to_tss"]) for row in associations if row.get("distance_to_tss") not in {None, ""}]
        record_counts = Counter(row.get("record_id") or "aggregate" for row in annotated)
        annotated_by_record = Counter((row.get("record_id") or "aggregate") for row in annotated if int(row.get("gene_count") or 0) > 0)
        metrics = {
            "schema_version": "1.0", "id": source["id"], "source_id": source["source_id"],
            "total_peaks": len(annotated), "annotated_peaks": annotated_count,
            "unassociated_peaks": len(annotated) - annotated_count,
            "category_distribution": dict(sorted(category_counts.items())),
            "unique_genes": len(genes),
            "mean_genes_per_peak": statistics.fmean(gene_counts) if gene_counts else 0.0,
            "distance_to_tss": distribution(distances),
            "peaks_by_chromosome": dict(sorted(chromosome_counts.items())),
            "status": "complete" if annotated else "complete_empty",
        }
        reports = Path(args.reports); reports.mkdir(parents=True, exist_ok=True)
        write_rows(reports / "category_distribution.tsv", ("category", "peak_count"), ({"category": key, "peak_count": value} for key, value in sorted(category_counts.items())))
        write_rows(reports / "peaks_by_chromosome.tsv", ("chromosome", "peak_count"), ({"chromosome": key, "peak_count": value} for key, value in sorted(chromosome_counts.items())))
        write_rows(reports / "by_record.tsv", ("record_id", "peak_count", "annotated_peaks"), ({"record_id": key, "peak_count": value, "annotated_peaks": annotated_by_record[key]} for key, value in sorted(record_counts.items())))
        write_rows(reports / "distance_to_tss.tsv", ("distance_to_tss",), ({"distance_to_tss": value} for value in distances))
        with open(args.output_json, "w", encoding="utf-8") as handle:
            json.dump(metrics, handle, indent=2, sort_keys=True); handle.write("\n")
        scalar = ("total_peaks", "annotated_peaks", "unassociated_peaks", "unique_genes", "mean_genes_per_peak")
        write_rows(args.output_tsv, ("metric", "value"), ({"metric": key, "value": metrics[key]} for key in scalar))
        ended = int(time.time())
        execution = {"schema_version": "1.0", "id": source["id"], "process": "PEAK_ANNOTATION_STATISTICS", "cpus": args.cpus, "memory_bytes": args.memory_bytes, "time": args.task_time, "started_epoch": started, "ended_epoch": ended, "elapsed_seconds": ended - started}
        with open(args.execution, "w", encoding="utf-8") as handle:
            json.dump(execution, handle, indent=2, sort_keys=True); handle.write("\n")
        with open(args.versions, "w", encoding="utf-8") as handle:
            handle.write(f'"PEAK_ANNOTATION_STATISTICS":\n    python: "{sys.version.split()[0]}"\n')
        manifest = {"schema_version": "1.0", "type": "peak_annotation_statistics", "id": source["id"], "source_id": source["source_id"], "record_id": source.get("record_id"), "record_ids": source.get("record_ids", []), "statistics": metrics, "annotation_manifest_sha256": sha256(args.annotation_manifest), "artifacts": {"statistics_json": {"path": Path(args.output_json).name, "sha256": sha256(args.output_json)}, "statistics_tsv": {"path": Path(args.output_tsv).name, "sha256": sha256(args.output_tsv)}, "reports": {"path": reports.name, "available": True}}, "execution": execution, "status": metrics["status"]}
        with open(args.manifest, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2, sort_keys=True); handle.write("\n")
    except (ValueError, KeyError, json.JSONDecodeError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr); return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
