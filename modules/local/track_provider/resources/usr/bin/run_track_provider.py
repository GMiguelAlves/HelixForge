#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import time


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def index_files(paths):
    result = {}
    for path in paths:
        name = os.path.basename(path)
        if name in result:
            raise ValueError(f"duplicate staged filename {name!r}")
        result[name] = path
    return result


def run(command, log, stdout=None):
    with open(log, "a", encoding="utf-8") as handle:
        handle.write(shlex.join([str(value) for value in command]) + "\n")
    result = subprocess.run(command, stdout=stdout, stderr=subprocess.PIPE, text=stdout is None, check=False)
    if result.returncode:
        error = result.stderr if isinstance(result.stderr, str) else result.stderr.decode("utf-8", "replace")
        raise ValueError(f"command failed ({result.returncode}): {shlex.join(command)}\n{error.strip()}")
    return result


def version(command, prefix=""):
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode:
        raise ValueError(f"cannot determine version for {command[0]}: {result.stderr.strip()}")
    return (result.stdout or result.stderr).splitlines()[0].strip().removeprefix(prefix)


def count_reads(bams, flag=None):
    total = 0
    for bam in bams:
        command = ["samtools", "view", "-c"]
        if flag is not None:
            command.extend(["-F", str(flag)])
        command.append(bam)
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode:
            raise ValueError(f"cannot count reads in {bam}: {result.stderr.strip()}")
        total += int(result.stdout.strip())
    return total


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    parser.add_argument("--bam", action="append", required=True)
    parser.add_argument("--bai", action="append", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--execution", required=True)
    parser.add_argument("--versions", required=True)
    parser.add_argument("--cpus", type=int, required=True)
    parser.add_argument("--memory-bytes", type=int, required=True)
    parser.add_argument("--task-time", required=True)
    parser.add_argument("--nextflow-version", required=True)
    args = parser.parse_args()
    started = int(time.time())
    try:
        with open(args.request, encoding="utf-8") as handle:
            request = json.load(handle)
        if request.get("status") not in {"valid", "stub"} or request.get("provider") != "deeptools_bamcoverage_v1":
            raise ValueError("TRACK_PROVIDER requires a validated deeptools_bamcoverage_v1 request")
        bam_index, bai_index = index_files(args.bam), index_files(args.bai)
        source_bams = []
        for source in request["sources"]:
            if source["bam"] not in bam_index or source["bai"] not in bai_index:
                raise ValueError(f"missing staged BAM/BAI for record {source['record_id']}")
            source_bams.append(bam_index[source["bam"]])
        output = Path(args.output_dir); reports = output / "provider_reports"
        reports.mkdir(parents=True, exist_ok=True)
        command_log = reports / "command.txt"; provider_log = reports / "provider.log"
        command_log.write_text("", encoding="utf-8")
        input_bam = source_bams[0]
        merged = None; merged_index = None
        if request["track_role"] == "aggregate":
            merged = output / "merged.bam"; merged_index = output / "merged.bam.bai"
            result = run(["samtools", "merge", "-@", str(args.cpus), "-f", str(merged), *source_bams], command_log)
            with provider_log.open("a", encoding="utf-8") as handle:
                handle.write(result.stderr or "")
            result = run(["samtools", "index", "-@", str(args.cpus), str(merged), str(merged_index)], command_log)
            with provider_log.open("a", encoding="utf-8") as handle:
                handle.write(result.stderr or "")
            input_bam = str(merged)
        parameters = request["parameters"]
        track = output / "track.bw"
        command = ["bamCoverage", "-b", input_bam, "-o", str(track), "-p", str(args.cpus), "--binSize", str(parameters["bin_size"]), "--normalizeUsing", parameters["normalization"]]
        if parameters["normalization"] == "RPGC":
            command.extend(["--effectiveGenomeSize", str(parameters["effective_genome_size"])])
        result = run(command, command_log)
        provider_log.write_text(result.stderr or "", encoding="utf-8")
        if not track.is_file() or track.stat().st_size == 0:
            raise ValueError("bamCoverage did not create a non-empty BigWig")
        metrics = {
            "schema_version": "1.0", "id": request["id"],
            "source_reads": count_reads(source_bams), "mapped_reads": count_reads(source_bams, 4),
            "track_bytes": track.stat().st_size, "source_bams": len(source_bams),
            "track_role": request["track_role"], "status": "complete",
        }
        with open(output / "provider_metrics.json", "w", encoding="utf-8") as handle:
            json.dump(metrics, handle, indent=2, sort_keys=True); handle.write("\n")
        ended = int(time.time())
        execution = {"schema_version": "1.0", "id": request["id"], "process": "TRACK_PROVIDER", "provider": request["provider"], "provider_version": request["provider_version"], "command": command, "cpus": args.cpus, "memory_bytes": args.memory_bytes, "time": args.task_time, "nextflow_version": args.nextflow_version, "started_epoch": started, "ended_epoch": ended, "elapsed_seconds": ended - started}
        with open(args.execution, "w", encoding="utf-8") as handle:
            json.dump(execution, handle, indent=2, sort_keys=True); handle.write("\n")
        deeptools_version = version(["bamCoverage", "--version"], "bamCoverage ")
        samtools_version = version(["samtools", "--version"], "samtools ")
        with open(args.versions, "w", encoding="utf-8") as handle:
            handle.write(f'"TRACK_PROVIDER":\n    deeptools: "{deeptools_version}"\n    samtools: "{samtools_version}"\n    python: "{sys.version.split()[0]}"\n')
        artifacts = {
            "primary_track": {"available": True, "path": "track.bw", "sha256": sha256(track)},
            "provider_metrics": {"available": True, "path": "provider_metrics.json", "sha256": sha256(output / "provider_metrics.json")},
            "merged_bam": {"available": merged is not None, "path": "merged.bam" if merged else None, "sha256": sha256(merged) if merged else None},
            "merged_bai": {"available": merged_index is not None, "path": "merged.bam.bai" if merged_index else None, "sha256": sha256(merged_index) if merged_index else None},
            "provider_reports": {"available": True, "path": "provider_reports"},
        }
        manifest = {
            "schema_version": "1.0", "type": "track_generation", "id": request["id"],
            "track_role": request["track_role"], "record_id": request.get("record_id"),
            "record_ids": request["record_ids"], "sample_ids": request["sample_ids"],
            "dataset": request.get("dataset"), "condition": request.get("condition"),
            "target": request.get("target"), "is_control": request.get("is_control"),
            "biological_replicates": request.get("biological_replicates", []),
            "technical_replicates": request.get("technical_replicates", []),
            "genome_id": request["genome_id"], "build": request["build"],
            "provider": request["provider"], "provider_version": request["provider_version"],
            "parameters": parameters, "sources": request["sources"], "reference": request["reference"],
            "artifacts": artifacts, "metrics": metrics, "execution": execution,
            "provenance": {"reference_manifest_sha256": request["reference_manifest"]["sha256"], "source_manifest_sha256": [source["manifest_sha256"] for source in request["sources"]]},
            "status": "complete",
        }
        with open(args.manifest, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2, sort_keys=True); handle.write("\n")
        with open(output / "manifest.json", "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2, sort_keys=True); handle.write("\n")
    except (ValueError, KeyError, json.JSONDecodeError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr); return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
