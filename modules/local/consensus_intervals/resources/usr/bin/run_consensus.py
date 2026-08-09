#!/usr/bin/env python3
import argparse
from collections import Counter
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


class CommandRunner:
    def __init__(self, command_log):
        self.command_log = command_log
        self.commands = []

    def run(self, command, stdout=None):
        command = [str(value) for value in command]
        self.commands.append(command)
        with open(self.command_log, "a", encoding="utf-8") as handle:
            handle.write(shlex.join(command) + "\n")
        if stdout is None:
            result = subprocess.run(command, capture_output=True, text=True, check=False)
        else:
            result = subprocess.run(command, stdout=stdout, stderr=subprocess.PIPE, check=False)
        if result.returncode:
            error = result.stderr if isinstance(result.stderr, str) else result.stderr.decode("utf-8", "replace")
            raise ValueError(f"command failed ({result.returncode}): {shlex.join(command)}\n{error.strip()}")
        return result


def index_directories(paths):
    result = {}
    for path in paths:
        name = os.path.basename(os.path.normpath(path))
        if name in result:
            raise ValueError(f"duplicate staged peak directory: {name}")
        result[name] = path
    return result


def write_evidence(replicates, directories, output):
    columns = (
        "replicate_id", "peak_id", "original_peak_name", "chrom", "start", "end",
        "score", "strand", "signal_value", "p_value", "q_value", "summit",
    )
    with open(output, "w", encoding="utf-8") as target:
        target.write("\t".join(columns) + "\n")
        for replicate in replicates:
            path = os.path.join(directories[replicate["peak_directory"]], replicate["peak_file"])
            with open(path, encoding="utf-8") as source:
                for line in source:
                    if not line.strip():
                        continue
                    fields = line.rstrip("\n").split("\t")
                    summit = fields[9] if replicate["peak_type"] == "narrow" else ""
                    values = (
                        replicate["evidence_replicate_id"], replicate["peak_id"], fields[3],
                        fields[0], fields[1], fields[2], fields[4], fields[5], fields[6],
                        fields[7], fields[8], summit,
                    )
                    target.write("\t".join(map(str, values)) + "\n")


def parse_multiinter(path, request, strategy, output_tsv, output_bed):
    threshold = int(request["support_threshold"])
    rows, support_distribution = [], Counter()
    with open(path, encoding="utf-8") as source:
        for line_number, line in enumerate(source, 1):
            if not line.strip():
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 5:
                raise ValueError(f"multiinter line {line_number}: expected at least 5 columns")
            try:
                start, end, support = int(fields[1]), int(fields[2]), int(fields[3])
            except ValueError as error:
                raise ValueError(f"multiinter line {line_number}: invalid numeric field: {error}")
            if start < 0 or end <= start or support < 1:
                raise ValueError(f"multiinter line {line_number}: invalid interval/support")
            support_distribution[support] += 1
            if support < threshold:
                continue
            support_replicates = fields[4]
            peak_id = f"{request['id']}.{strategy}.{len(rows) + 1:06d}"
            rows.append({
                "peak_id": peak_id, "chrom": fields[0], "start": start, "end": end,
                "support": support, "support_replicates": support_replicates,
            })
    with open(output_tsv, "w", encoding="utf-8") as handle:
        handle.write("peak_id\tchrom\tstart\tend\tsupport\tsupport_replicates\n")
        for row in rows:
            handle.write("{peak_id}\t{chrom}\t{start}\t{end}\t{support}\t{support_replicates}\n".format(**row))
    with open(output_bed, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(f"{row['chrom']}\t{row['start']}\t{row['end']}\t{row['peak_id']}\n")
    return rows, dict(sorted(support_distribution.items()))


def first_line(command):
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode:
        raise ValueError(f"cannot determine {command[0]} version: {result.stderr.strip()}")
    return (result.stdout or result.stderr).splitlines()[0].strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    parser.add_argument("--peak-dir", action="append", required=True)
    parser.add_argument("--strategy", required=True, choices=("union", "intersection", "replicate_support"))
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--reports", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--execution", required=True)
    parser.add_argument("--versions", required=True)
    parser.add_argument("--cpus", type=int, required=True)
    parser.add_argument("--memory-bytes", type=int, required=True)
    parser.add_argument("--task-time", required=True)
    parser.add_argument("--nextflow-version", required=True)
    parser.add_argument("--environment", required=True)
    args = parser.parse_args()
    started = int(time.time())
    try:
        with open(args.request, encoding="utf-8") as handle:
            request = json.load(handle)
        if request.get("status") != "valid" or request.get("strategy") != args.strategy:
            raise ValueError("provider strategy does not match a validated Consensus request")
        if request.get("provider") != "bedtools_multiinter":
            raise ValueError("Consensus interval provider received an incompatible provider request")
        directories = index_directories(args.peak_dir)
        reports = Path(args.reports)
        output_dir = Path(args.output_dir)
        reports.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        runner = CommandRunner(reports / "commands.txt")

        merged_paths, names = [], []
        for index, replicate in enumerate(request["replicates"], 1):
            if replicate["peak_directory"] not in directories:
                raise ValueError(f"missing staged peak directory {replicate['peak_directory']}")
            source = Path(directories[replicate["peak_directory"]]) / replicate["peak_file"]
            sorted_path = reports / f"replicate_{index:03d}.sorted.bed"
            merged_path = reports / f"replicate_{index:03d}.merged.bed"
            with open(sorted_path, "wb") as output:
                runner.run(["bedtools", "sort", "-i", source], stdout=output)
            with open(merged_path, "wb") as output:
                runner.run(["bedtools", "merge", "-i", sorted_path], stdout=output)
            merged_paths.append(merged_path)
            names.append(replicate["evidence_replicate_id"])

        multiinter = reports / "multiinter.atomic.tsv"
        command = ["bedtools", "multiinter", "-i", *merged_paths, "-names", *names]
        with open(multiinter, "wb") as output:
            runner.run(command, stdout=output)
        evidence = reports / "replicate_evidence.tsv"
        write_evidence(request["replicates"], directories, evidence)
        result_tsv = output_dir / "consolidated_peaks.tsv"
        result_bed = output_dir / "consolidated_peaks.bed"
        rows, support_distribution = parse_multiinter(multiinter, request, args.strategy, result_tsv, result_bed)
        shutil.copy2(evidence, output_dir / "replicate_evidence.tsv")
        statistics = {
            "schema_version": "1.0", "id": request["id"], "strategy": args.strategy,
            "replicate_count": request["replicate_count"],
            "support_threshold": request["support_threshold"],
            "atomic_segments": sum(support_distribution.values()),
            "consolidated_peaks": len(rows),
            "support_distribution": {str(key): value for key, value in support_distribution.items()},
            "status": "complete" if rows else "complete_empty",
        }
        statistics_path = output_dir / "statistics.json"
        with open(statistics_path, "w", encoding="utf-8") as handle:
            json.dump(statistics, handle, indent=2, sort_keys=True)
            handle.write("\n")
        ended = int(time.time())
        execution = {
            "schema_version": "1.0", "id": request["id"], "process": "CONSENSUS_INTERVALS",
            "strategy": args.strategy, "commands": runner.commands, "cpus": args.cpus,
            "memory_bytes": args.memory_bytes, "time": args.task_time,
            "nextflow_version": args.nextflow_version, "environment": args.environment,
            "started_epoch": started, "ended_epoch": ended, "elapsed_seconds": ended - started,
        }
        with open(args.execution, "w", encoding="utf-8") as handle:
            json.dump(execution, handle, indent=2, sort_keys=True)
            handle.write("\n")
        bedtools_version = first_line(["bedtools", "--version"]).removeprefix("bedtools v")
        with open(args.versions, "w", encoding="utf-8") as handle:
            handle.write(f'"CONSENSUS_INTERVALS":\n    bedtools: "{bedtools_version}"\n    python: "{sys.version.split()[0]}"\n')
        manifest = {
            "schema_version": "1.0", "type": "consensus", "id": request["id"],
            "strategy": args.strategy, "provider": request["provider"],
            "provider_version": request["provider_version"],
            "dataset": request["dataset"], "experiment_id": request["experiment_id"],
            "condition": request["condition"], "treatment": request.get("treatment"),
            "target": request["target"], "genome_id": request["genome_id"],
            "peak_type": request["peak_type"], "caller": request["caller"],
            "caller_version": request["caller_version"],
            "replicate_mode": request["replicate_mode"],
            "replicate_policy": request["replicate_policy"],
            "replicates": request["replicates"], "parameters": request["parameters"],
            "statistics": statistics,
            "artifacts": {
                "consolidated_peaks": {"available": True, "path": "consolidated_peaks.tsv", "sha256": sha256(result_tsv)},
                "consolidated_bed": {"available": True, "path": "consolidated_peaks.bed", "sha256": sha256(result_bed)},
                "replicate_evidence": {"available": True, "path": "replicate_evidence.tsv", "sha256": sha256(output_dir / "replicate_evidence.tsv")},
            },
            "execution": execution, "status": statistics["status"],
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
