#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def index_directories(paths):
    result = {}
    for path in paths:
        name = os.path.basename(os.path.normpath(path))
        if name in result:
            raise ValueError(f"duplicate staged peak directory: {name}")
        result[name] = path
    return result


def validate_request(request, directories):
    if request.get("status") != "valid" or request.get("strategy") != "idr":
        raise ValueError("IDR provider requires a validated strategy=idr request")
    if request.get("provider") != "idr_pending":
        raise ValueError("IDR provider identity is incompatible")
    if request.get("replicate_mode") != "biological" or request.get("replicate_policy") != "require_premerged":
        raise ValueError("IDR v1 requires premerged biological replicates")
    if request.get("replicate_count") != 2 or len(request.get("replicates", [])) != 2:
        raise ValueError("IDR v1 requires exactly two biological replicates")
    if request.get("peak_type") != "narrow":
        raise ValueError("IDR v1 accepts narrowPeak only")
    for replicate in request["replicates"]:
        directory_name = replicate["peak_directory"]
        if directory_name not in directories:
            raise ValueError(f"missing staged peak directory {directory_name}")
        peak_file = os.path.join(directories[directory_name], replicate["peak_file"])
        if not os.path.isfile(peak_file):
            raise ValueError(f"missing IDR peak input: {peak_file}")
    return request


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    parser.add_argument("--peak-dir", action="append", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--reports", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--execution", required=True)
    parser.add_argument("--versions", required=True)
    parser.add_argument("--nextflow-version", required=True)
    args = parser.parse_args()
    started = int(time.time())
    try:
        with open(args.request, encoding="utf-8") as handle:
            request = json.load(handle)
        directories = index_directories(args.peak_dir)
        validate_request(request, directories)
        output_dir = Path(args.output_dir)
        reports = Path(args.reports)
        output_dir.mkdir(parents=True, exist_ok=True)
        reports.mkdir(parents=True, exist_ok=True)
        provider_request = {
            "schema_version": "1.0", "id": request["id"], "strategy": "idr",
            "provider": "idr", "provider_runtime": "not_implemented",
            "idr_threshold": request["parameters"]["idr_threshold"],
            "rank_metric": request["parameters"]["rank_metric"],
            "peak_type": request["peak_type"],
            "replicates": [
                {
                    "evidence_replicate_id": replicate["evidence_replicate_id"],
                    "peak_id": replicate["peak_id"],
                    "peak_file": replicate["peak_file"],
                    "peak_sha256": sha256(os.path.join(directories[replicate["peak_directory"]], replicate["peak_file"])),
                }
                for replicate in request["replicates"]
            ],
            "status": "not_implemented",
        }
        provider_request_path = output_dir / "provider_request.json"
        with open(provider_request_path, "w", encoding="utf-8") as handle:
            json.dump(provider_request, handle, indent=2, sort_keys=True)
            handle.write("\n")
        with open(reports / "provider.log", "w", encoding="utf-8") as handle:
            handle.write("IDR runtime was not executed. Provider abstraction validated inputs only.\n")
        ended = int(time.time())
        execution = {
            "schema_version": "1.0", "id": request["id"], "process": "IDR_PROVIDER",
            "strategy": "idr", "nextflow_version": args.nextflow_version,
            "started_epoch": started, "ended_epoch": ended, "elapsed_seconds": ended - started,
            "status": "not_implemented",
        }
        with open(args.execution, "w", encoding="utf-8") as handle:
            json.dump(execution, handle, indent=2, sort_keys=True)
            handle.write("\n")
        with open(args.versions, "w", encoding="utf-8") as handle:
            handle.write(f'"IDR_PROVIDER":\n    provider_runtime: not_implemented\n    python: "{sys.version.split()[0]}"\n')
        manifest = {
            "schema_version": "1.0", "type": "idr", "id": request["id"],
            "strategy": "idr", "provider": "idr_pending", "provider_version": "0.1.0",
            "dataset": request["dataset"], "experiment_id": request["experiment_id"],
            "condition": request["condition"], "treatment": request.get("treatment"),
            "target": request["target"], "genome_id": request["genome_id"],
            "peak_type": request["peak_type"], "caller": request["caller"],
            "caller_version": request["caller_version"],
            "replicate_mode": request["replicate_mode"],
            "replicate_policy": request["replicate_policy"],
            "replicates": request["replicates"], "parameters": request["parameters"],
            "artifacts": {
                "consolidated_peaks": {"available": False, "reason": "IDR runtime is not implemented or scientifically validated"},
                "provider_request": {"available": True, "path": "provider_request.json", "sha256": sha256(provider_request_path)},
            },
            "execution": execution, "status": "not_implemented",
        }
        with open(args.manifest, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2, sort_keys=True)
            handle.write("\n")
        shutil.copy2(args.manifest, output_dir / "manifest.json")
    except (ValueError, KeyError, json.JSONDecodeError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
