#!/usr/bin/env python3
import argparse
import base64
import hashlib
import json
import os
import shutil
import statistics
import time


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
        "min": min(values), "max": max(values), "mean": statistics.fmean(values),
        "median": statistics.median(values),
    }


def validate_peaks(path, peak_type):
    expected_columns = 10 if peak_type == "narrow" else 9
    widths, scores, signals = [], [], []
    contigs = set()
    with open(path, encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            columns = line.rstrip("\n").split("\t")
            if len(columns) != expected_columns:
                raise ValueError(
                    f"line {line_number}: {peak_type}Peak requires {expected_columns} columns, found {len(columns)}"
                )
            try:
                start, end = int(columns[1]), int(columns[2])
                score, signal = float(columns[4]), float(columns[6])
            except ValueError as error:
                raise ValueError(f"line {line_number}: invalid numeric peak field: {error}")
            if start < 0 or end <= start:
                raise ValueError(f"line {line_number}: invalid half-open coordinates {columns[0]}:{start}-{end}")
            if not columns[0] or any(char.isspace() for char in columns[0]):
                raise ValueError(f"line {line_number}: invalid contig name {columns[0]!r}")
            contigs.add(columns[0])
            widths.append(end - start)
            scores.append(score)
            signals.append(signal)
    return {
        "total_peaks": len(widths), "contigs_with_peaks": len(contigs),
        "peak_width": distribution(widths), "peak_score": distribution(scores),
        "signal_value": distribution(signals),
    }


def copy_optional(source, target):
    if os.path.isfile(source):
        shutil.copy2(source, target)
        return {"available": True, "path": os.path.basename(target), "sha256": sha256(target)}
    return {"available": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request-base64", required=True)
    parser.add_argument("--provider-peaks", required=True)
    parser.add_argument("--provider-dir", required=True)
    parser.add_argument("--provider-manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--metrics-json", required=True)
    parser.add_argument("--metrics-tsv", required=True)
    args = parser.parse_args()
    request = json.loads(base64.b64decode(args.request_base64).decode("utf-8"))
    started = int(time.time())
    os.makedirs(args.output_dir, exist_ok=True)
    peak_type = request["peak_type"]
    extension = "narrowPeak" if peak_type == "narrow" else "broadPeak"
    semantic_peak = os.path.join(args.output_dir, f"peaks.{extension}")
    shutil.copy2(args.provider_peaks, semantic_peak)
    metrics = validate_peaks(semantic_peak, peak_type)
    metrics.update({
        "schema_version": "1.0", "id": request["peak_id"], "caller": request["caller"],
        "caller_version": request["caller_version"], "peak_type": peak_type,
    })
    with open(args.metrics_json, "w", encoding="utf-8") as handle:
        json.dump(metrics, handle, indent=2, sort_keys=True)
        handle.write("\n")
    with open(args.metrics_tsv, "w", encoding="utf-8") as handle:
        handle.write("metric\tvalue\n")
        handle.write(f"total_peaks\t{metrics['total_peaks']}\n")
        handle.write(f"contigs_with_peaks\t{metrics['contigs_with_peaks']}\n")
        for group in ("peak_width", "peak_score", "signal_value"):
            for statistic_name, value in metrics[group].items():
                handle.write(f"{group}_{statistic_name}\t{'' if value is None else value}\n")

    raw_target = os.path.join(args.output_dir, "caller_outputs")
    shutil.copytree(args.provider_dir, raw_target)
    summit_source = os.path.join(args.provider_dir, f"{request['peak_id']}_summits.bed")
    treatment_signal_source = os.path.join(args.provider_dir, f"{request['peak_id']}_treat_pileup.bdg")
    control_signal_source = os.path.join(args.provider_dir, f"{request['peak_id']}_control_lambda.bdg")
    artifacts = {
        "peaks": {"available": True, "path": f"peaks.{extension}", "sha256": sha256(semantic_peak)},
        "narrowPeak": {"available": peak_type == "narrow", "path": "peaks.narrowPeak" if peak_type == "narrow" else None},
        "broadPeak": {"available": peak_type == "broad", "path": "peaks.broadPeak" if peak_type == "broad" else None},
        "summit": copy_optional(summit_source, os.path.join(args.output_dir, "summits.bed")),
        "treatment_signal": copy_optional(treatment_signal_source, os.path.join(args.output_dir, "treatment_signal.bdg")),
        "control_signal": copy_optional(control_signal_source, os.path.join(args.output_dir, "control_signal.bdg")),
        "caller_outputs": {"available": True, "path": "caller_outputs"},
        "peak_statistics": {"available": True, "path": os.path.basename(args.metrics_json), "sha256": sha256(args.metrics_json)},
    }
    ended = int(time.time())
    manifest = {
        "schema_version": "1.0", "type": "peak_calling", "id": request["peak_id"],
        "sample_id": request["sample_id"], "record_id": request["record_id"],
        "experiment_id": request["experiment_id"], "target": request["target"],
        "biological_replicate": request["biological_replicate"],
        "technical_replicate": request["technical_replicate"],
        "control_id": request.get("control_id") or None,
        "control_record_id": request.get("control_record_id") or None,
        "caller": request["caller"], "caller_version": request["caller_version"],
        "peak_type": peak_type, "parameters": request, "metrics": metrics,
        "artifacts": artifacts, "provider_manifest_sha256": sha256(args.provider_manifest),
        "execution": {"started_epoch": started, "ended_epoch": ended, "elapsed_seconds": ended - started},
        "status": "complete" if metrics["total_peaks"] else "complete_empty",
    }
    manifest_path = os.path.join(args.output_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")
    shutil.copy2(manifest_path, args.manifest)
    shutil.copy2(args.metrics_json, os.path.join(args.output_dir, "peak_metrics.json"))
    shutil.copy2(args.metrics_tsv, os.path.join(args.output_dir, "peak_metrics.tsv"))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(2)
