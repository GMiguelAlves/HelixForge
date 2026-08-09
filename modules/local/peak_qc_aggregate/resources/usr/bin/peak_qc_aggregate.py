#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import sys
import time


IDENTITY_FIELDS = (
    "record_id", "sample_id", "target", "biological_replicate",
    "technical_replicate", "peak_type", "caller", "caller_version",
)


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_unique(paths, expected_type):
    records = {}
    for path in paths:
        with open(path, encoding="utf-8") as handle:
            document = json.load(handle)
        if document.get("type") != expected_type:
            raise ValueError(f"{path}: expected manifest type {expected_type!r}, found {document.get('type')!r}")
        identifier = str(document.get("id", ""))
        if not identifier:
            raise ValueError(f"{path}: manifest id is empty")
        if identifier in records:
            raise ValueError(f"duplicate {expected_type} manifest id: {identifier}")
        records[identifier] = (document, path)
    if not records:
        raise ValueError(f"no {expected_type} manifests were provided")
    return records


def combine(frip_records, statistics_records):
    frip_ids, statistics_ids = set(frip_records), set(statistics_records)
    if frip_ids != statistics_ids:
        missing_frip = sorted(statistics_ids - frip_ids)
        missing_statistics = sorted(frip_ids - statistics_ids)
        raise ValueError(f"Peak QC manifest mismatch; missing FRiP={missing_frip}, missing statistics={missing_statistics}")
    rows = []
    for identifier in sorted(frip_ids):
        frip = frip_records[identifier][0]
        statistics = statistics_records[identifier][0]
        for field in IDENTITY_FIELDS:
            if str(frip.get(field, "")) != str(statistics.get(field, "")):
                raise ValueError(f"{identifier}: FRiP and peak statistics disagree on {field}")
        fm, sm = frip["metrics"], statistics["metrics"]
        rows.append({
            "peak_id": identifier,
            **{field: frip.get(field) for field in IDENTITY_FIELDS},
            "control_id": frip.get("control_id"),
            "control_record_id": frip.get("control_record_id"),
            "unit": fm["unit"], "peak_count": sm["peak_count"],
            "valid_peak_count": sm["valid_peak_count"],
            "frip": fm["frip"], "total_units": fm["total_units"],
            "units_in_peaks": fm["units_in_peaks"],
            "total_alignments_input": fm["total_alignments_input"],
            "eligible_alignments": fm["eligible_alignments"],
            "peak_width_min": sm["peak_width"]["min"],
            "peak_width_max": sm["peak_width"]["max"],
            "peak_width_mean": sm["peak_width"]["mean"],
            "peak_width_median": sm["peak_width"]["median"],
            "peak_score_mean": sm["peak_score"]["mean"],
            "peak_score_median": sm["peak_score"]["median"],
            "signal_value_mean": sm["signal_value"]["mean"],
            "signal_value_median": sm["signal_value"]["median"],
        })
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--frip-manifest", action="append", required=True)
    parser.add_argument("--statistics-manifest", action="append", required=True)
    parser.add_argument("--summary-json", required=True)
    parser.add_argument("--summary-tsv", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--execution", required=True)
    parser.add_argument("--versions", required=True)
    parser.add_argument("--cpus", type=int, required=True)
    parser.add_argument("--memory-bytes", type=int, required=True)
    parser.add_argument("--task-time", required=True)
    args = parser.parse_args()
    started = int(time.time())
    try:
        frip_records = load_unique(args.frip_manifest, "peak_qc_frip")
        statistics_records = load_unique(args.statistics_manifest, "peak_qc_peak_statistics")
        rows = combine(frip_records, statistics_records)
        columns = list(rows[0])
        with open(args.summary_tsv, "w", encoding="utf-8") as handle:
            handle.write("\t".join(columns) + "\n")
            for row in rows:
                handle.write("\t".join("" if row[column] is None else str(row[column]) for column in columns) + "\n")
        summary = {"schema_version": "1.0", "type": "peak_qc_summary", "records": len(rows), "rows": rows, "status": "complete"}
        with open(args.summary_json, "w", encoding="utf-8") as handle:
            json.dump(summary, handle, indent=2, sort_keys=True)
            handle.write("\n")
        ended = int(time.time())
        execution = {
            "schema_version": "1.0", "id": "chipseq.peak_qc.aggregate", "process": "PEAK_QC_AGGREGATE",
            "cpus": args.cpus, "memory_bytes": args.memory_bytes, "time": args.task_time,
            "started_epoch": started, "ended_epoch": ended, "elapsed_seconds": ended - started,
        }
        with open(args.execution, "w", encoding="utf-8") as handle:
            json.dump(execution, handle, indent=2, sort_keys=True)
            handle.write("\n")
        with open(args.versions, "w", encoding="utf-8") as handle:
            handle.write(f'"PEAK_QC_AGGREGATE":\n    python: "{sys.version.split()[0]}"\n')
        manifest = {
            "schema_version": "1.0", "type": "peak_qc", "records": len(rows),
            "replicate_ids": [row["peak_id"] for row in rows],
            "frip_manifests": [{"path": os.path.basename(path), "sha256": sha256(path)} for path in args.frip_manifest],
            "statistics_manifests": [{"path": os.path.basename(path), "sha256": sha256(path)} for path in args.statistics_manifest],
            "artifacts": {
                "qc_summary": {"path": os.path.basename(args.summary_tsv), "sha256": sha256(args.summary_tsv)},
                "qc_summary_json": {"path": os.path.basename(args.summary_json), "sha256": sha256(args.summary_json)},
            },
            "execution": execution, "status": "complete",
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
