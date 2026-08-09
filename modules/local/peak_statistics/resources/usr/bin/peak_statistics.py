#!/usr/bin/env python3
import argparse
from collections import Counter
import hashlib
import json
import math
import os
import statistics
import sys
import time


EXPECTED_COLUMNS = {"narrow": 10, "broad": 9}


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def distribution(values):
    if not values:
        return {"min": None, "max": None, "mean": None, "median": None}
    return {
        "min": min(values), "max": max(values),
        "mean": statistics.fmean(values), "median": statistics.median(values),
    }


def parse_peaks(path, peak_type):
    expected = EXPECTED_COLUMNS[peak_type]
    records = []
    with open(path, encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            columns = line.rstrip("\n").split("\t")
            if len(columns) != expected:
                raise ValueError(f"line {line_number}: {peak_type}Peak requires {expected} columns, found {len(columns)}")
            try:
                start, end = int(columns[1]), int(columns[2])
                score, signal = float(columns[4]), float(columns[6])
            except ValueError as error:
                raise ValueError(f"line {line_number}: invalid numeric peak field: {error}")
            if not all(math.isfinite(value) for value in (score, signal)):
                raise ValueError(f"line {line_number}: score and signalValue must be finite")
            if start < 0 or end <= start:
                raise ValueError(f"line {line_number}: invalid half-open coordinates {columns[0]}:{start}-{end}")
            if not columns[0] or any(char.isspace() for char in columns[0]):
                raise ValueError(f"line {line_number}: invalid contig name {columns[0]!r}")
            records.append({
                "index": len(records) + 1, "chromosome": columns[0], "start": start,
                "end": end, "name": columns[3], "width": end - start,
                "score": score, "signal_value": signal,
            })
    return records


def calculate(records, request):
    widths = [row["width"] for row in records]
    scores = [row["score"] for row in records]
    signals = [row["signal_value"] for row in records]
    by_chromosome = dict(sorted(Counter(row["chromosome"] for row in records).items()))
    return {
        "schema_version": "1.0", "id": request["id"],
        "record_id": request["record_id"], "sample_id": request["sample_id"],
        "target": request["target"],
        "biological_replicate": request["biological_replicate"],
        "technical_replicate": request["technical_replicate"],
        "peak_type": request["peak_type"], "caller": request["caller"],
        "caller_version": request["caller_version"],
        "peak_count": len(records), "valid_peak_count": len(records),
        "invalid_peak_count": 0, "peak_width": distribution(widths),
        "peak_score": distribution(scores), "signal_value": distribution(signals),
        "peaks_by_chromosome": by_chromosome,
        "status": "complete" if records else "complete_empty",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    parser.add_argument("--peaks", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--reports", required=True)
    parser.add_argument("--versions", required=True)
    parser.add_argument("--execution", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--cpus", type=int, required=True)
    parser.add_argument("--memory-bytes", type=int, required=True)
    parser.add_argument("--task-time", required=True)
    args = parser.parse_args()
    started = int(time.time())
    try:
        if not os.path.isfile(args.request) or os.path.getsize(args.request) == 0:
            raise ValueError("Peak QC request is missing or empty")
        if not os.path.isfile(args.peaks):
            raise ValueError("peak file is missing")
        with open(args.request, encoding="utf-8") as handle:
            request = json.load(handle)
        peak_type = request.get("peak_type")
        if peak_type not in EXPECTED_COLUMNS:
            raise ValueError(f"peak_type must be narrow or broad, got {peak_type!r}")
        records = parse_peaks(args.peaks, peak_type)
        metrics = calculate(records, request)
        os.makedirs(args.reports, exist_ok=True)
        with open(args.output_json, "w", encoding="utf-8") as handle:
            json.dump(metrics, handle, indent=2, sort_keys=True)
            handle.write("\n")
        with open(os.path.join(args.reports, "summary.tsv"), "w", encoding="utf-8") as handle:
            handle.write("metric\tvalue\n")
            for key in ("peak_count", "valid_peak_count", "invalid_peak_count"):
                handle.write(f"{key}\t{metrics[key]}\n")
            for group in ("peak_width", "peak_score", "signal_value"):
                for key, value in metrics[group].items():
                    handle.write(f"{group}_{key}\t{'' if value is None else value}\n")
        with open(os.path.join(args.reports, "peak_width_distribution.tsv"), "w", encoding="utf-8") as handle:
            handle.write("peak_index\tpeak_name\tchromosome\twidth\n")
            for row in records:
                handle.write(f"{row['index']}\t{row['name']}\t{row['chromosome']}\t{row['width']}\n")
        with open(os.path.join(args.reports, "peaks_by_chromosome.tsv"), "w", encoding="utf-8") as handle:
            handle.write("chromosome\tpeak_count\n")
            for chromosome, count in metrics["peaks_by_chromosome"].items():
                handle.write(f"{chromosome}\t{count}\n")
        ended = int(time.time())
        execution = {
            "schema_version": "1.0", "id": request["id"], "process": "PEAK_STATISTICS",
            "command": ["peak_statistics.py", "--request", os.path.basename(args.request),
                        "--peaks", os.path.basename(args.peaks)],
            "cpus": args.cpus, "memory_bytes": args.memory_bytes, "time": args.task_time,
            "started_epoch": started, "ended_epoch": ended, "elapsed_seconds": ended - started,
        }
        with open(args.execution, "w", encoding="utf-8") as handle:
            json.dump(execution, handle, indent=2, sort_keys=True)
            handle.write("\n")
        with open(args.versions, "w", encoding="utf-8") as handle:
            handle.write(f'"PEAK_STATISTICS":\n    python: "{sys.version.split()[0]}"\n')
        manifest = {
            "schema_version": "1.0", "type": "peak_qc_peak_statistics", "id": request["id"],
            "record_id": request["record_id"], "sample_id": request["sample_id"],
            "target": request["target"],
            "biological_replicate": request["biological_replicate"],
            "technical_replicate": request["technical_replicate"],
            "peak_type": request["peak_type"], "caller": request["caller"],
            "caller_version": request["caller_version"], "metrics": metrics,
            "inputs": {"peaks": {"path": os.path.basename(args.peaks), "sha256": sha256(args.peaks)},
                       "request": {"path": os.path.basename(args.request), "sha256": sha256(args.request)}},
            "execution": execution, "status": metrics["status"],
        }
        with open(args.manifest, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2, sort_keys=True)
            handle.write("\n")
    except (ValueError, KeyError, json.JSONDecodeError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
