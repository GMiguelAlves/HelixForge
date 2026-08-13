#!/usr/bin/env python3
"""Run the official IDR provider and materialize the Consensus API contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path


PROVIDER_VERSION = "2.0.4.2"
RANK_OPTIONS = {
    "signal_value": "signal.value",
    "p_value": "p.value",
    "q_value": "q.value",
}


def sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def index_directories(paths: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in paths:
        name = os.path.basename(os.path.normpath(path))
        if name in result:
            raise ValueError(f"duplicate staged peak directory: {name}")
        result[name] = path
    return result


def validate_narrow_peak(path: str | Path, rank_metric: str) -> int:
    rank_index = {"signal_value": 6, "p_value": 7, "q_value": 8}[rank_metric]
    rows = 0
    with open(path, encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 10:
                raise ValueError(f"{path}:{line_number}: expected 10 narrowPeak columns")
            try:
                start, end = int(fields[1]), int(fields[2])
                rank = float(fields[rank_index])
            except ValueError as error:
                raise ValueError(f"{path}:{line_number}: invalid coordinate/rank: {error}")
            if start < 0 or end <= start or not math.isfinite(rank) or rank < 0:
                raise ValueError(f"{path}:{line_number}: invalid half-open interval or rank")
            rows += 1
    if rows == 0:
        raise ValueError(f"IDR peak input is empty: {path}")
    return rows


def validate_request(request: dict, directories: dict[str, str]) -> tuple[dict, list[Path]]:
    if request.get("status") != "valid" or request.get("strategy") != "idr":
        raise ValueError("IDR provider requires a validated strategy=idr request")
    if request.get("provider") != "idr" or request.get("provider_version") != PROVIDER_VERSION:
        raise ValueError("IDR provider identity/version is incompatible")
    if request.get("replicate_mode") != "biological" or request.get("replicate_policy") != "require_premerged":
        raise ValueError("IDR v1 requires premerged biological replicates")
    if request.get("replicate_count") != 2 or len(request.get("replicates", [])) != 2:
        raise ValueError("IDR v1 requires exactly two biological replicates")
    if request.get("peak_type") != "narrow":
        raise ValueError("IDR v1 accepts narrowPeak only")
    parameters = request.get("parameters", {})
    rank_metric = parameters.get("rank_metric")
    if rank_metric not in RANK_OPTIONS:
        raise ValueError("IDR rank_metric is unsupported")
    threshold = parameters.get("idr_threshold")
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not 0 < threshold <= 1:
        raise ValueError("IDR threshold must be > 0 and <= 1")
    peak_paths: list[Path] = []
    for replicate in request["replicates"]:
        directory_name = replicate["peak_directory"]
        if directory_name not in directories:
            raise ValueError(f"missing staged peak directory {directory_name}")
        peak_file = Path(directories[directory_name]) / replicate["peak_file"]
        if not peak_file.is_file():
            raise ValueError(f"missing IDR peak input: {peak_file}")
        replicate["input_peak_count"] = validate_narrow_peak(peak_file, rank_metric)
        peak_paths.append(peak_file)
    return request, peak_paths


def build_command(request: dict, peak_paths: list[Path], output: Path, log: Path) -> list[str]:
    parameters = request["parameters"]
    return [
        "idr",
        "--samples", str(peak_paths[0]), str(peak_paths[1]),
        "--input-file-type", "narrowPeak",
        "--output-file-type", "narrowPeak",
        "--rank", RANK_OPTIONS[parameters["rank_metric"]],
        "--idr-threshold", str(parameters["idr_threshold"]),
        "--soft-idr-threshold", str(parameters["idr_threshold"]),
        "--random-seed", "0",
        "--plot",
        "--output-file", str(output),
        "--log-output-file", str(log),
    ]


def idr_probability(score: float) -> float:
    return 0.0 if math.isinf(score) else 10.0 ** (-score)


def parse_idr_output(source: Path, group_id: str, table: Path, bed: Path) -> int:
    columns = [
        "peak_id", "chrom", "start", "end", "name", "score", "strand",
        "signal_value", "p_value", "q_value", "summit", "local_idr_score",
        "global_idr_score", "local_idr", "global_idr",
    ]
    parsed = []
    with source.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip() or line.startswith("#"):
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 12:
                raise ValueError(f"IDR output line {line_number}: expected at least 12 columns")
            try:
                start, end = int(fields[1]), int(fields[2])
                local_score, global_score = float(fields[10]), float(fields[11])
            except ValueError as error:
                raise ValueError(f"IDR output line {line_number}: invalid numeric value: {error}")
            if start < 0 or end <= start or local_score < 0 or global_score < 0:
                raise ValueError(f"IDR output line {line_number}: invalid interval/IDR score")
            peak_id = f"{group_id}.idr.{len(parsed) + 1:06d}"
            parsed.append([
                peak_id, fields[0], start, end, fields[3], fields[4], fields[5],
                fields[6], fields[7], fields[8], fields[9], fields[10], fields[11],
                f"{idr_probability(local_score):.12g}", f"{idr_probability(global_score):.12g}",
            ])
    with table.open("w", encoding="utf-8") as handle:
        handle.write("\t".join(columns) + "\n")
        for row in parsed:
            handle.write("\t".join(map(str, row)) + "\n")
    with bed.open("w", encoding="utf-8") as handle:
        for row in parsed:
            handle.write(f"{row[1]}\t{row[2]}\t{row[3]}\t{row[0]}\n")
    return len(parsed)


def command_version() -> str:
    completed = subprocess.run(["idr", "--version"], capture_output=True, text=True, check=False)
    if completed.returncode:
        raise RuntimeError(f"cannot determine IDR version: {completed.stderr.strip()}")
    return (completed.stdout or completed.stderr).strip().split()[-1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    parser.add_argument("--peak-dir", action="append", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--reports", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--execution", required=True)
    parser.add_argument("--versions", required=True)
    parser.add_argument("--nextflow-version", required=True)
    parser.add_argument("--cpus", required=True, type=int)
    parser.add_argument("--memory-bytes", required=True, type=int)
    parser.add_argument("--task-time", required=True)
    parser.add_argument("--environment", required=True)
    args = parser.parse_args()
    started = int(time.time())
    try:
        with open(args.request, encoding="utf-8") as handle:
            request = json.load(handle)
        directories = index_directories(args.peak_dir)
        request, peak_paths = validate_request(request, directories)
        output_dir, reports = Path(args.output_dir), Path(args.reports)
        output_dir.mkdir(parents=True, exist_ok=True)
        reports.mkdir(parents=True, exist_ok=True)
        raw_output = reports / "idr_output.narrowPeak"
        provider_log = reports / "idr.log"
        command = build_command(request, peak_paths, raw_output, provider_log)
        (reports / "command.txt").write_text(shlex.join(command) + "\n", encoding="utf-8")
        (reports / "command.json").write_text(json.dumps(command, indent=2) + "\n", encoding="utf-8")
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        (reports / "idr.stdout.log").write_text(completed.stdout, encoding="utf-8")
        (reports / "idr.stderr.log").write_text(completed.stderr, encoding="utf-8")
        if completed.returncode:
            raise RuntimeError(f"IDR failed with exit status {completed.returncode}")
        if not raw_output.is_file():
            raise RuntimeError("IDR did not create its output file")

        result_table = output_dir / "consolidated_peaks.tsv"
        result_bed = output_dir / "consolidated_peaks.bed"
        passing = parse_idr_output(raw_output, request["id"], result_table, result_bed)
        shutil.copy2(raw_output, output_dir / "idr_output.narrowPeak")
        plot_source = Path(str(raw_output) + ".png")
        if plot_source.is_file():
            shutil.copy2(plot_source, output_dir / "idr_plot.png")

        evidence_path = output_dir / "replicate_evidence.tsv"
        with evidence_path.open("w", encoding="utf-8") as handle:
            handle.write("replicate_id\tpeak_id\tpeak_file\tpeak_sha256\tinput_peaks\n")
            for replicate, peak_path in zip(request["replicates"], peak_paths):
                handle.write(
                    f"{replicate['evidence_replicate_id']}\t{replicate['peak_id']}\t"
                    f"{peak_path.name}\t{sha256(peak_path)}\t{replicate['input_peak_count']}\n"
                )
        status = "complete" if passing else "complete_empty"
        statistics = {
            "schema_version": "1.0", "id": request["id"], "strategy": "idr",
            "idr_threshold": request["parameters"]["idr_threshold"],
            "rank_metric": request["parameters"]["rank_metric"],
            "random_seed": 0, "input_peaks": [item["input_peak_count"] for item in request["replicates"]],
            "consolidated_peaks": passing, "status": status,
        }
        statistics_path = output_dir / "statistics.json"
        statistics_path.write_text(json.dumps(statistics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        observed_version = command_version()
        ended = int(time.time())
        execution = {
            "schema_version": "1.0", "id": request["id"], "process": "IDR_PROVIDER",
            "strategy": "idr", "command": command, "command_shell": shlex.join(command),
            "cpus": args.cpus, "memory_bytes": args.memory_bytes, "time": args.task_time,
            "nextflow_version": args.nextflow_version, "environment": args.environment,
            "started_epoch": started, "ended_epoch": ended, "elapsed_seconds": ended - started,
            "status": status,
        }
        Path(args.execution).write_text(json.dumps(execution, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        Path(args.versions).write_text(
            f'"IDR_PROVIDER":\n    idr: "{observed_version}"\n    package: "{PROVIDER_VERSION}"\n    python: "{sys.version.split()[0]}"\n',
            encoding="utf-8",
        )
        artifacts = {
            "consolidated_peaks": {"available": True, "path": result_table.name, "sha256": sha256(result_table)},
            "consolidated_bed": {"available": True, "path": result_bed.name, "sha256": sha256(result_bed)},
            "idr_output": {"available": True, "path": "idr_output.narrowPeak", "sha256": sha256(output_dir / "idr_output.narrowPeak")},
            "idr_plot": {"available": (output_dir / "idr_plot.png").is_file(), "path": "idr_plot.png"},
            "replicate_evidence": {"available": True, "path": evidence_path.name, "sha256": sha256(evidence_path)},
            "statistics": {"available": True, "path": statistics_path.name, "sha256": sha256(statistics_path)},
        }
        manifest = {
            "schema_version": "1.0", "type": "idr", "id": request["id"],
            "strategy": "idr", "provider": "idr", "provider_version": PROVIDER_VERSION,
            "dataset": request["dataset"], "experiment_id": request["experiment_id"],
            "condition": request["condition"], "treatment": request.get("treatment"),
            "target": request["target"], "genome_id": request["genome_id"], "build": request["genome_id"],
            "peak_type": request["peak_type"], "caller": request["caller"],
            "caller_version": request["caller_version"], "replicate_mode": request["replicate_mode"],
            "replicate_policy": request["replicate_policy"], "replicates": request["replicates"],
            "parameters": request["parameters"], "statistics": statistics,
            "artifacts": artifacts, "execution": execution, "status": status,
        }
        Path(args.manifest).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        shutil.copy2(args.manifest, output_dir / "manifest.json")
    except (ValueError, KeyError, json.JSONDecodeError, OSError, RuntimeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
