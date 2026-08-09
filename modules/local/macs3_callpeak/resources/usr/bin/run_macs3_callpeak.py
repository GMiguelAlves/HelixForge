#!/usr/bin/env python3
import argparse
import base64
import hashlib
import json
import os
import shlex
import subprocess
import sys
import time


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request-base64", required=True)
    parser.add_argument("--treatment", required=True)
    parser.add_argument("--control", default="")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--provider-peak", required=True)
    parser.add_argument("--reports", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--execution", required=True)
    parser.add_argument("--cpus", required=True, type=int)
    parser.add_argument("--memory-bytes", required=True, type=int)
    parser.add_argument("--task-time", required=True)
    parser.add_argument("--environment", required=True)
    args = parser.parse_args()

    request = json.loads(base64.b64decode(args.request_base64).decode("utf-8"))
    for label, path in (("treatment BAM", args.treatment), ("control BAM", args.control)):
        if path and (not os.path.isfile(path) or os.path.getsize(path) == 0):
            raise ValueError(f"{label} is missing or empty: {path}")
    os.makedirs(args.output_dir, exist_ok=True)
    os.makedirs(args.reports, exist_ok=True)
    peak_id = request["peak_id"]
    command = [
        "macs3", "callpeak", "-t", args.treatment,
        "-f", request["format"], "-g", str(request["effective_genome_size"]),
        "-n", peak_id, "--outdir", args.output_dir,
        "--keep-dup", str(request["duplicate_policy"]), "-B",
    ]
    if args.control:
        command.extend(["-c", args.control])
    if request["cutoff_type"] == "p_value":
        command.extend(["-p", str(request["cutoff"])])
    else:
        command.extend(["-q", str(request["cutoff"])])
    if request["peak_type"] == "broad":
        command.append("--broad")
    command.extend(shlex.split(request.get("additional_args", "")))

    with open(os.path.join(args.reports, "command.json"), "w", encoding="utf-8") as handle:
        json.dump(command, handle, indent=2)
        handle.write("\n")
    with open(os.path.join(args.reports, "command.txt"), "w", encoding="utf-8") as handle:
        handle.write(shlex.join(command) + "\n")
    started = int(time.time())
    with open(os.path.join(args.reports, "macs3.stdout.log"), "w", encoding="utf-8") as stdout, open(
        os.path.join(args.reports, "macs3.stderr.log"), "w", encoding="utf-8"
    ) as stderr:
        completed = subprocess.run(command, stdout=stdout, stderr=stderr, check=False)
    ended = int(time.time())
    if completed.returncode:
        raise RuntimeError(f"MACS3 failed with exit code {completed.returncode}; see macs3.stderr.log")

    extension = "broadPeak" if request["peak_type"] == "broad" else "narrowPeak"
    source_peak = os.path.join(args.output_dir, f"{peak_id}_peaks.{extension}")
    if not os.path.isfile(source_peak):
        raise RuntimeError(f"MACS3 did not create the expected {extension} file: {source_peak}")
    with open(source_peak, "rb") as source, open(args.provider_peak, "wb") as target:
        target.write(source.read())

    treatment_sha = sha256(args.treatment)
    control_sha = sha256(args.control) if args.control else None
    peak_sha = sha256(args.provider_peak)
    execution = {
        "schema_version": "1.0", "id": peak_id, "process": "MACS3_CALLPEAK",
        "command": command, "command_shell": shlex.join(command),
        "treatment_bam": os.path.basename(args.treatment), "treatment_sha256": treatment_sha,
        "control_bam": os.path.basename(args.control) if args.control else None,
        "control_sha256": control_sha, "reference": request.get("reference"),
        "reference_sha256": request.get("reference_sha256"),
        "caller": "macs3", "caller_version": request["caller_version"],
        "parameters": request, "cpus": args.cpus, "memory_bytes": args.memory_bytes,
        "time": args.task_time, "environment": args.environment,
        "started_epoch": started, "ended_epoch": ended, "elapsed_seconds": ended - started,
    }
    with open(args.execution, "w", encoding="utf-8") as handle:
        json.dump(execution, handle, indent=2, sort_keys=True)
        handle.write("\n")
    manifest = {
        "schema_version": "1.0", "type": "peak_calling_provider", "id": peak_id,
        "caller": "macs3", "caller_version": request["caller_version"],
        "peak_type": request["peak_type"], "sample_id": request["sample_id"],
        "record_id": request["record_id"], "target": request["target"],
        "control_id": request.get("control_id") or None,
        "control_record_id": request.get("control_record_id") or None,
        "artifacts": {"peaks": {"path": os.path.basename(args.provider_peak), "sha256": peak_sha}},
        "inputs": {"treatment_sha256": treatment_sha, "control_sha256": control_sha},
        "parameters": request,
    }
    with open(args.manifest, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, RuntimeError, KeyError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(2)
