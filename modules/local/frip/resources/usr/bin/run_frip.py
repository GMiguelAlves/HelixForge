#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
from pathlib import Path
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


def require_file(path, label, allow_empty=False):
    if not os.path.isfile(path) or (not allow_empty and os.path.getsize(path) == 0):
        raise ValueError(f"{label} is missing or empty: {path}")


class CommandRunner:
    def __init__(self, command_log):
        self.command_log = command_log
        self.commands = []

    def run(self, command, stdout=None):
        command = [str(value) for value in command]
        self.commands.append(command)
        with open(self.command_log, "a", encoding="utf-8") as log:
            log.write(shlex.join(command) + "\n")
        if stdout is None:
            result = subprocess.run(command, capture_output=True, text=True, check=False)
        else:
            result = subprocess.run(command, stdout=stdout, stderr=subprocess.PIPE, check=False)
        if result.returncode:
            message = result.stderr if isinstance(result.stderr, str) else result.stderr.decode("utf-8", "replace")
            raise ValueError(f"command failed ({result.returncode}): {shlex.join(command)}\n{message.strip()}")
        return result


def count_lines(path):
    with open(path, encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def first_line(command):
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode:
        raise ValueError(f"cannot determine version for {command[0]}: {result.stderr.strip()}")
    return (result.stdout or result.stderr).splitlines()[0].strip()


def bedpe_to_fragments(source, destination):
    seen = set()
    with open(source, encoding="utf-8") as input_handle, open(destination, "w", encoding="utf-8") as output_handle:
        for line_number, line in enumerate(input_handle, 1):
            if not line.strip():
                continue
            columns = line.rstrip("\n").split("\t")
            if len(columns) < 10:
                raise ValueError(f"BEDPE line {line_number}: expected at least 10 columns")
            chrom_a, chrom_b, name = columns[0], columns[3], columns[6]
            if chrom_a in {".", ""} or chrom_b in {".", ""} or chrom_a != chrom_b:
                raise ValueError(f"BEDPE line {line_number}: paired template {name!r} is not a same-contig fragment")
            if name in seen:
                raise ValueError(f"BEDPE line {line_number}: template {name!r} occurs more than once after primary filtering")
            seen.add(name)
            try:
                start = min(int(columns[1]), int(columns[4]))
                end = max(int(columns[2]), int(columns[5]))
            except ValueError as error:
                raise ValueError(f"BEDPE line {line_number}: invalid coordinate: {error}")
            if start < 0 or end <= start:
                raise ValueError(f"BEDPE line {line_number}: invalid fragment coordinates {chrom_a}:{start}-{end}")
            output_handle.write(f"{chrom_a}\t{start}\t{end}\t{name}\n")
    return len(seen)


def bed_to_reads(source, destination):
    count = 0
    with open(source, encoding="utf-8") as input_handle, open(destination, "w", encoding="utf-8") as output_handle:
        for line_number, line in enumerate(input_handle, 1):
            if not line.strip():
                continue
            columns = line.rstrip("\n").split("\t")
            if len(columns) < 6:
                raise ValueError(f"BED line {line_number}: expected at least 6 columns")
            output_handle.write("\t".join(columns[:6]) + "\n")
            count += 1
    return count


def samtools_count(runner, bam):
    result = runner.run(["samtools", "view", "-c", bam])
    try:
        return int(result.stdout.strip())
    except ValueError:
        raise ValueError(f"samtools returned an invalid count for {bam}: {result.stdout!r}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    parser.add_argument("--bam", required=True)
    parser.add_argument("--bai", required=True)
    parser.add_argument("--peaks", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-tsv", required=True)
    parser.add_argument("--reports", required=True)
    parser.add_argument("--versions", required=True)
    parser.add_argument("--execution", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--cpus", type=int, required=True)
    parser.add_argument("--memory-bytes", type=int, required=True)
    parser.add_argument("--task-time", required=True)
    parser.add_argument("--environment", required=True)
    args = parser.parse_args()
    started = int(time.time())
    try:
        for path, label in ((args.request, "Peak QC request"), (args.bam, "BAM"), (args.bai, "BAI")):
            require_file(path, label)
        require_file(args.peaks, "peaks", allow_empty=True)
        with open(args.request, encoding="utf-8") as handle:
            request = json.load(handle)
        if request.get("status") != "valid":
            raise ValueError("Peak QC request was not validated by PEAK_QC_CONTEXT")
        reports = Path(args.reports)
        reports.mkdir(parents=True, exist_ok=True)
        runner = CommandRunner(reports / "commands.txt")

        sorted_peaks = reports / "peaks.sorted.bed"
        merged_peaks = reports / "merged_peaks.bed"
        with open(sorted_peaks, "wb") as output:
            runner.run(["bedtools", "sort", "-i", args.peaks], stdout=output)
        with open(merged_peaks, "wb") as output:
            runner.run(["bedtools", "merge", "-i", sorted_peaks], stdout=output)

        filters = request["filters"]
        eligible_bam = reports / "eligible.bam"
        view_command = ["samtools", "view", "-@", args.cpus, "-b", "-q", filters["min_mapq"]]
        if filters["include_flags"]:
            view_command.extend(["-f", filters["include_flags"]])
        if filters["exclude_flags"]:
            view_command.extend(["-F", filters["exclude_flags"]])
        view_command.extend(["-o", eligible_bam, args.bam])
        runner.run(view_command)

        unit_bed = reports / "eligible_units.bed"
        if request["unit"] == "fragments":
            name_bam = reports / "eligible.name.bam"
            runner.run(["samtools", "sort", "-n", "-@", args.cpus, "-o", name_bam, eligible_bam])
            raw_bed = reports / "eligible.bedpe"
            with open(raw_bed, "wb") as output:
                runner.run(["bedtools", "bamtobed", "-bedpe", "-i", name_bam], stdout=output)
            denominator = bedpe_to_fragments(raw_bed, unit_bed)
        elif request["unit"] == "reads":
            raw_bed = reports / "eligible.reads.bed"
            with open(raw_bed, "wb") as output:
                runner.run(["bedtools", "bamtobed", "-i", eligible_bam], stdout=output)
            denominator = bed_to_reads(raw_bed, unit_bed)
        else:
            raise ValueError(f"unsupported resolved unit {request['unit']!r}")
        if denominator == 0:
            raise ValueError("FRiP denominator is zero after applying the explicit alignment filters")

        overlapping = reports / "units_in_peaks.bed"
        with open(overlapping, "wb") as output:
            runner.run(["bedtools", "intersect", "-u", "-a", unit_bed, "-b", merged_peaks], stdout=output)
        numerator = count_lines(overlapping)
        frip = numerator / denominator
        total_alignments = samtools_count(runner, args.bam)
        eligible_alignments = samtools_count(runner, eligible_bam)
        metrics = {
            "schema_version": "1.0",
            "id": request["id"],
            "record_id": request["record_id"],
            "sample_id": request["sample_id"],
            "target": request["target"],
            "biological_replicate": request["biological_replicate"],
            "technical_replicate": request["technical_replicate"],
            "peak_type": request["peak_type"],
            "caller": request["caller"],
            "caller_version": request["caller_version"],
            "unit": request["unit"],
            "frip": frip,
            "total_units": denominator,
            "units_in_peaks": numerator,
            "total_alignments_input": total_alignments,
            "eligible_alignments": eligible_alignments,
            "peak_intervals_original": request["peak_count_validated"],
            "peak_intervals_merged": count_lines(merged_peaks),
            "filters": filters,
            "overlap_strategy": request["overlap_strategy"],
            "blacklist_policy": request["blacklist_policy"],
            "status": "complete",
        }
        with open(args.output_json, "w", encoding="utf-8") as handle:
            json.dump(metrics, handle, indent=2, sort_keys=True)
            handle.write("\n")
        unit_label = "fragments" if request["unit"] == "fragments" else "reads"
        with open(args.output_tsv, "w", encoding="utf-8") as handle:
            handle.write("metric\tvalue\n")
            for key, value in (
                ("frip", frip), (f"total_{unit_label}", denominator),
                (f"{unit_label}_in_peaks", numerator), ("total_alignments_input", total_alignments),
                ("eligible_alignments", eligible_alignments),
                ("peak_intervals_original", request["peak_count_validated"]),
                ("peak_intervals_merged", metrics["peak_intervals_merged"]),
            ):
                handle.write(f"{key}\t{value}\n")

        ended = int(time.time())
        execution = {
            "schema_version": "1.0", "id": request["id"], "process": "FRIP",
            "commands": runner.commands, "cpus": args.cpus, "memory_bytes": args.memory_bytes,
            "time": args.task_time, "environment": args.environment,
            "started_epoch": started, "ended_epoch": ended, "elapsed_seconds": ended - started,
        }
        with open(args.execution, "w", encoding="utf-8") as handle:
            json.dump(execution, handle, indent=2, sort_keys=True)
            handle.write("\n")
        samtools_version = first_line(["samtools", "--version"]).removeprefix("samtools ")
        bedtools_version = first_line(["bedtools", "--version"]).removeprefix("bedtools v")
        with open(args.versions, "w", encoding="utf-8") as handle:
            handle.write(f'"FRIP":\n    samtools: "{samtools_version}"\n    bedtools: "{bedtools_version}"\n    python: "{sys.version.split()[0]}"\n')
        manifest = {
            "schema_version": "1.0", "type": "peak_qc_frip", "id": request["id"],
            "record_id": request["record_id"], "sample_id": request["sample_id"],
            "target": request["target"], "control_id": request.get("control_id"),
            "control_record_id": request.get("control_record_id"),
            "biological_replicate": request["biological_replicate"],
            "technical_replicate": request["technical_replicate"],
            "peak_type": request["peak_type"], "caller": request["caller"],
            "caller_version": request["caller_version"], "metrics": metrics,
            "parameters": {"unit": request["unit"], "filters": filters,
                           "overlap_strategy": request["overlap_strategy"],
                           "blacklist_policy": request["blacklist_policy"]},
            "inputs": request["inputs"],
            "artifacts": {
                "frip": {"path": os.path.basename(args.output_json), "sha256": sha256(args.output_json)},
                "metrics": {"path": os.path.basename(args.output_tsv), "sha256": sha256(args.output_tsv)},
                "merged_peaks": {"path": str(merged_peaks.name), "sha256": sha256(merged_peaks)},
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
