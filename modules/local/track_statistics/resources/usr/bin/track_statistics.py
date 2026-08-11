#!/usr/bin/env python3
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import sys
import time


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_rows(path, columns, rows):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--track-dir", required=True)
    parser.add_argument("--track-manifest", required=True)
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
        import pyBigWig
        with open(args.track_manifest, encoding="utf-8") as handle:
            source = json.load(handle)
        if source.get("type") != "track_generation":
            raise ValueError("TRACK_STATISTICS requires a track_generation manifest")
        root = Path(args.track_dir); track = root / source["artifacts"]["primary_track"]["path"]
        with open(root / source["artifacts"]["provider_metrics"]["path"], encoding="utf-8") as handle:
            provider_metrics = json.load(handle)
        bw = pyBigWig.open(str(track))
        chroms = bw.chroms()
        rows, values, number_of_bins, bases_covered = [], [], 0, 0
        weighted_sum = 0.0
        for chrom, length in sorted(chroms.items()):
            intervals = bw.intervals(chrom) or []
            chrom_bases = 0
            for start, end, value in intervals:
                width = end - start
                if width < 1 or not math.isfinite(value):
                    continue
                number_of_bins += 1; chrom_bases += width; bases_covered += width
                weighted_sum += value * width; values.append(value)
            rows.append({"contig": chrom, "length": length, "intervals": len(intervals), "bases_covered": chrom_bases})
        bw.close()
        depth = {"available": bool(values), "min": min(values) if values else None, "max": max(values) if values else None, "mean": weighted_sum / bases_covered if bases_covered else None}
        metrics = {
            "schema_version": "1.0", "id": source["id"], "track_role": source["track_role"],
            "source_reads": provider_metrics.get("source_reads"), "mapped_reads": provider_metrics.get("mapped_reads"),
            "contigs": len(chroms), "bases_covered": bases_covered, "depth": depth,
            "number_of_bins": number_of_bins, "track_bytes": track.stat().st_size,
            "normalization": source["parameters"]["normalization"],
            "scale_factor": source["parameters"]["scale_factor"], "parameters": source["parameters"],
            "status": "complete",
        }
        reports = Path(args.reports); reports.mkdir(parents=True, exist_ok=True)
        write_rows(reports / "contigs.tsv", ("contig", "length", "intervals", "bases_covered"), rows)
        with open(args.output_json, "w", encoding="utf-8") as handle:
            json.dump(metrics, handle, indent=2, sort_keys=True); handle.write("\n")
        keys = ("source_reads", "mapped_reads", "contigs", "bases_covered", "number_of_bins", "track_bytes", "normalization", "scale_factor")
        write_rows(args.output_tsv, ("metric", "value"), ({"metric": key, "value": metrics[key]} for key in keys))
        ended = int(time.time())
        execution = {"schema_version": "1.0", "id": source["id"], "process": "TRACK_STATISTICS", "cpus": args.cpus, "memory_bytes": args.memory_bytes, "time": args.task_time, "started_epoch": started, "ended_epoch": ended, "elapsed_seconds": ended - started}
        with open(args.execution, "w", encoding="utf-8") as handle:
            json.dump(execution, handle, indent=2, sort_keys=True); handle.write("\n")
        with open(args.versions, "w", encoding="utf-8") as handle:
            handle.write(f'"TRACK_STATISTICS":\n    python: "{sys.version.split()[0]}"\n    pyBigWig: "{pyBigWig.__version__}"\n')
        manifest = {"schema_version": "1.0", "type": "track_statistics", "id": source["id"], "track_role": source["track_role"], "record_id": source.get("record_id"), "record_ids": source["record_ids"], "track_manifest_sha256": sha256(args.track_manifest), "statistics": metrics, "artifacts": {"statistics_json": {"path": Path(args.output_json).name, "sha256": sha256(args.output_json)}, "statistics_tsv": {"path": Path(args.output_tsv).name, "sha256": sha256(args.output_tsv)}, "contigs": {"path": "contigs.tsv", "sha256": sha256(reports / "contigs.tsv")}}, "execution": execution, "status": "complete"}
        with open(args.manifest, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2, sort_keys=True); handle.write("\n")
    except (ImportError, ValueError, KeyError, json.JSONDecodeError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr); return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
