#!/usr/bin/env python3
import argparse
import csv
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


def load_json(path, label):
    with open(path, encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def index_files(paths, label):
    result = {}
    for path in paths:
        name = os.path.basename(path)
        if name in result:
            raise ValueError(f"duplicate staged {label} basename: {name}")
        result[name] = path
    return result


def bed_to_saf(path, output):
    rows = []
    seen = set()
    with open(path, encoding="utf-8") as source, open(output, "w", encoding="utf-8", newline="") as target:
        writer = csv.writer(target, delimiter="\t", lineterminator="\n")
        writer.writerow(["GeneID", "Chr", "Start", "End", "Strand"])
        for line_number, line in enumerate(source, 1):
            if not line.strip():
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 4:
                raise ValueError(f"peak BED line {line_number}: expected BED4")
            peak_id, chrom = fields[3], fields[0]
            try:
                start, end = int(fields[1]), int(fields[2])
            except ValueError as error:
                raise ValueError(f"peak BED line {line_number}: invalid coordinates: {error}")
            if not peak_id or peak_id in seen or start < 0 or end <= start:
                raise ValueError(f"peak BED line {line_number}: invalid or duplicate peak identity")
            seen.add(peak_id)
            rows.append((peak_id, chrom, start, end))
            writer.writerow([peak_id, chrom, start + 1, end, "."])
    if not rows:
        raise ValueError("peak universe is empty")
    return rows


def resolve_inputs(spec, bams, bais, manifests):
    bam_index, bai_index = index_files(bams, "BAM"), index_files(bais, "BAI")
    manifest_docs = {}
    for path in manifests:
        document = load_json(path, "final BAM manifest")
        identifier = str(document.get("id", ""))
        if document.get("type") != "bam_final" or not identifier or identifier in manifest_docs:
            raise ValueError(f"invalid or duplicate final BAM manifest id: {identifier!r}")
        manifest_docs[identifier] = (document, path)
    resolved = []
    for sample in spec.get("samples", []):
        record_id = sample.get("record_id")
        if record_id not in manifest_docs:
            raise ValueError(f"sample {record_id}: final BAM manifest is missing")
        document, manifest_path = manifest_docs[record_id]
        if document.get("sample_id") not in {None, "", sample.get("sample_id")}:
            raise ValueError(f"sample {record_id}: BAM manifest sample_id mismatch")
        bam_name = sample.get("bam_file") or document.get("artifact") or f"{record_id}.filtered.bam"
        bai_name = sample.get("bai_file") or document.get("index") or f"{bam_name}.bai"
        bam_name, bai_name = os.path.basename(bam_name), os.path.basename(bai_name)
        if bam_name not in bam_index or bai_name not in bai_index:
            raise ValueError(f"sample {record_id}: BAM/BAI artifacts are missing")
        bam_path, bai_path = bam_index[bam_name], bai_index[bai_name]
        if document.get("sha256") and sha256(bam_path) != document["sha256"]:
            raise ValueError(f"sample {record_id}: BAM checksum mismatch")
        if document.get("index_sha256") and sha256(bai_path) != document["index_sha256"]:
            raise ValueError(f"sample {record_id}: BAI checksum mismatch")
        resolved.append({**sample, "bam": bam_path, "bai": bai_path, "bam_manifest": manifest_path,
                         "bam_sha256": sha256(bam_path), "bai_sha256": sha256(bai_path),
                         "duplicate_policy": document.get("duplicate_policy"),
                         "blacklist_policy": document.get("blacklist_policy")})
    if len(resolved) < 2:
        raise ValueError("peak counting requires at least two samples")
    return resolved


def provider_command(spec, saf, output, samples, cpus):
    counting = spec["counting"]
    if counting.get("provider") != "featurecounts":
        raise ValueError("FEATURECOUNTS_PEAK requires provider=featurecounts")
    if counting.get("overlap_policy") != "any" or counting.get("allow_multi_overlap") is not False:
        raise ValueError("v1 requires overlap_policy=any and allow_multi_overlap=false")
    if counting.get("allow_multimapping") is not False or counting.get("fractional") is not False:
        raise ValueError("v1 rejects multimapping and fractional peak counts")
    strandedness = int(counting.get("strandedness", 0))
    if strandedness not in {0, 1, 2}:
        raise ValueError("strandedness must be 0, 1, or 2")
    min_mapq = int(counting.get("min_mapq", 0))
    if min_mapq < 0:
        raise ValueError("min_mapq must be non-negative")
    layouts = {sample.get("layout") for sample in samples}
    if layouts - {"single", "paired"} or len(layouts) != 1:
        raise ValueError("one count model requires one explicit single/paired layout")
    paired = layouts == {"paired"}
    unit = counting.get("unit")
    if (paired and unit != "fragments") or (not paired and unit != "reads"):
        raise ValueError("counting unit must be fragments for paired layout and reads for single layout")
    command = ["featureCounts", "-T", str(cpus), "-F", "SAF", "-a", str(saf), "-o", str(output),
               "-Q", str(min_mapq), "-s", str(strandedness)]
    if paired:
        command.extend(["-p", "--countReadPairs"])
        if counting.get("require_both_ends_mapped", True):
            command.append("-B")
        if counting.get("exclude_chimeric", True):
            command.append("-C")
    command.extend(str(sample["bam"]) for sample in samples)
    return command


def convert_counts(native_path, peaks, samples, output):
    with open(native_path, encoding="utf-8") as handle:
        rows = [line.rstrip("\n").split("\t") for line in handle if line.strip() and not line.startswith("#")]
    if not rows or len(rows[0]) != 6 + len(samples):
        raise ValueError("featureCounts output columns do not match the explicit sample map")
    by_id = {row[0]: row for row in rows[1:]}
    with open(output, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(["peak_id", "chrom", "start", "end", *[sample["sample_id"] for sample in samples]])
        for peak_id, chrom, start, end in peaks:
            if peak_id not in by_id:
                raise ValueError(f"featureCounts omitted peak {peak_id}")
            values = by_id[peak_id][6:]
            try:
                counts = [int(value) for value in values]
            except ValueError:
                raise ValueError(f"featureCounts returned a non-integer count for {peak_id}")
            writer.writerow([peak_id, chrom, start, end, *counts])


def first_line(command):
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode:
        raise ValueError(f"cannot determine featureCounts version: {result.stderr.strip()}")
    return (result.stdout or result.stderr).splitlines()[0].strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--peaks", required=True)
    parser.add_argument("--bam", action="append", required=True)
    parser.add_argument("--bai", action="append", required=True)
    parser.add_argument("--bam-manifest", action="append", required=True)
    parser.add_argument("--spec", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--reports", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--execution", required=True)
    parser.add_argument("--versions", required=True)
    parser.add_argument("--cpus", type=int, required=True)
    parser.add_argument("--memory-bytes", type=int, required=True)
    parser.add_argument("--task-time", required=True)
    parser.add_argument("--nextflow-version", required=True)
    parser.add_argument("--profile", default="")
    parser.add_argument("--git-commit", default="unknown")
    parser.add_argument("--environment", default="host")
    args = parser.parse_args()
    started = int(time.time())
    try:
        spec = load_json(args.spec, "count specification")
        output_dir, reports = Path(args.output_dir), Path(args.reports)
        output_dir.mkdir(parents=True, exist_ok=True)
        reports.mkdir(parents=True, exist_ok=True)
        peaks = bed_to_saf(args.peaks, reports / "peaks.saf")
        samples = resolve_inputs(spec, args.bam, args.bai, args.bam_manifest)
        native = reports / "featurecounts.txt"
        command = provider_command(spec, reports / "peaks.saf", native, samples, args.cpus)
        (reports / "command.txt").write_text(shlex.join(command) + "\n", encoding="utf-8")
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        (reports / "featurecounts.stdout.log").write_text(result.stdout, encoding="utf-8")
        (reports / "featurecounts.stderr.log").write_text(result.stderr, encoding="utf-8")
        if result.returncode:
            raise ValueError(f"featureCounts failed with exit status {result.returncode}")
        summary_source = Path(str(native) + ".summary")
        if not summary_source.is_file():
            raise ValueError("featureCounts summary is missing")
        shutil.copy2(summary_source, output_dir / "featurecounts_summary.tsv")
        raw_counts = output_dir / "raw_peak_counts.tsv"
        convert_counts(native, peaks, samples, raw_counts)
        shutil.copy2(args.spec, output_dir / "count_spec.json")
        ended = int(time.time())
        execution = {
            "schema_version": "1.0", "id": spec["analysis_id"], "process": "FEATURECOUNTS_PEAK",
            "command": command, "cpus": args.cpus, "memory_bytes": args.memory_bytes,
            "time": args.task_time, "nextflow_version": args.nextflow_version,
            "profile": args.profile, "git_commit": args.git_commit, "environment": args.environment,
            "peak_sha256": sha256(args.peaks), "spec_sha256": sha256(args.spec),
            "samples": [{key: value for key, value in sample.items() if key not in {"bam", "bai", "bam_manifest"}} for sample in samples],
            "started_epoch": started, "ended_epoch": ended, "elapsed_seconds": ended - started,
        }
        Path(args.execution).write_text(json.dumps(execution, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        version = first_line(["featureCounts", "-v"]).replace("featureCounts v", "")
        Path(args.versions).write_text(f'"FEATURECOUNTS_PEAK":\n    featurecounts: "{version}"\n    python: "{sys.version.split()[0]}"\n', encoding="utf-8")
        manifest = {
            "schema_version": "1.0", "type": "peak_count_matrix", "id": spec["analysis_id"],
            "provider": "featurecounts", "provider_version": version,
            "genome_id": spec["genome_id"], "peak_type": spec["peak_type"],
            "samples": [{"record_id": sample["record_id"], "sample_id": sample["sample_id"],
                         "biological_replicate": sample["biological_replicate"], "condition": sample["condition"]} for sample in samples],
            "counting": spec["counting"], "inputs": {"peak_sha256": sha256(args.peaks), "spec_sha256": sha256(args.spec)},
            "artifacts": {"raw_counts": {"path": "raw_peak_counts.tsv", "sha256": sha256(raw_counts), "available": True},
                          "summary": {"path": "featurecounts_summary.tsv", "sha256": sha256(output_dir / "featurecounts_summary.tsv"), "available": True}},
            "execution": execution, "status": "complete",
        }
        Path(args.manifest).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        shutil.copy2(args.manifest, output_dir / "manifest.json")
    except (ValueError, KeyError, OSError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
