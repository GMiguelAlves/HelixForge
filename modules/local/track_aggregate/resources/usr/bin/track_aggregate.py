#!/usr/bin/env python3
import argparse
import csv
import hashlib
import json
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


def load_by_id(paths, expected_type):
    result = {}
    for path in paths:
        with open(path, encoding="utf-8") as handle:
            document = json.load(handle)
        if document.get("type") != expected_type:
            raise ValueError(f"{path}: expected type={expected_type}")
        identifier = document.get("id")
        if not identifier or identifier in result:
            raise ValueError(f"empty or duplicate track id {identifier!r}")
        result[identifier] = (document, path)
    return result


def index_dirs(paths):
    result = {}
    for path in paths:
        with open(Path(path) / "manifest.json", encoding="utf-8") as handle:
            identifier = json.load(handle).get("id")
        if not identifier or identifier in result:
            raise ValueError(f"empty or duplicate track directory id {identifier!r}")
        result[identifier] = Path(path)
    return result


def write_rows(path, columns, rows):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", lineterminator="\n", extrasaction="ignore")
        writer.writeheader(); writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--track-dir", action="append", required=True)
    parser.add_argument("--track-manifest", action="append", required=True)
    parser.add_argument("--statistics-json", action="append", required=True)
    parser.add_argument("--statistics-manifest", action="append", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--execution", required=True)
    parser.add_argument("--versions", required=True)
    parser.add_argument("--cpus", type=int, required=True)
    parser.add_argument("--memory-bytes", type=int, required=True)
    parser.add_argument("--task-time", required=True)
    args = parser.parse_args()
    started = int(time.time())
    try:
        tracks = load_by_id(args.track_manifest, "track_generation")
        statistics_manifests = load_by_id(args.statistics_manifest, "track_statistics")
        directories = index_dirs(args.track_dir)
        statistics = {}
        for path in args.statistics_json:
            with open(path, encoding="utf-8") as handle:
                document = json.load(handle)
            identifier = document.get("id")
            if not identifier or identifier in statistics:
                raise ValueError(f"empty or duplicate statistics id {identifier!r}")
            statistics[identifier] = document
        identities = set(tracks)
        if identities != set(statistics_manifests) or identities != set(directories) or identities != set(statistics):
            raise ValueError("track artifacts/manifests/statistics disagree on IDs")
        output = Path(args.output_dir); output.mkdir(parents=True, exist_ok=True)
        track_output = output / "tracks"; track_output.mkdir(exist_ok=True)
        rows, references = [], []
        for identifier in sorted(identities):
            document, manifest_path = tracks[identifier]
            source = directories[identifier] / document["artifacts"]["primary_track"]["path"]
            target = track_output / f"{identifier}.bw"
            shutil.copy2(source, target)
            metric = statistics[identifier]
            rows.append({
                "track_id": identifier, "track_role": document["track_role"],
                "record_id": document.get("record_id") or "", "record_ids": ";".join(document["record_ids"]),
                "sample_ids": ";".join(document["sample_ids"]), "dataset": document.get("dataset") or "",
                "condition": document.get("condition") or "", "target": document.get("target") or "",
                "genome_id": document["genome_id"], "build": document["build"],
                "normalization": document["parameters"]["normalization"], "bin_size": document["parameters"]["bin_size"],
                "track": f"tracks/{target.name}", "track_sha256": sha256(target),
                "source_reads": metric.get("source_reads"), "mapped_reads": metric.get("mapped_reads"),
                "bases_covered": metric.get("bases_covered"), "number_of_bins": metric.get("number_of_bins"),
                "status": document["status"],
            })
            references.append({"id": identifier, "manifest_sha256": sha256(manifest_path), "statistics_manifest_sha256": sha256(statistics_manifests[identifier][1])})
        columns = ("track_id", "track_role", "record_id", "record_ids", "sample_ids", "dataset", "condition", "target", "genome_id", "build", "normalization", "bin_size", "track", "track_sha256", "source_reads", "mapped_reads", "bases_covered", "number_of_bins", "status")
        write_rows(output / "tracks.tsv", columns, rows)
        ended = int(time.time())
        execution = {"schema_version": "1.0", "id": "chipseq.tracks.aggregate", "process": "TRACK_AGGREGATE", "cpus": args.cpus, "memory_bytes": args.memory_bytes, "time": args.task_time, "started_epoch": started, "ended_epoch": ended, "elapsed_seconds": ended - started}
        with open(args.execution, "w", encoding="utf-8") as handle:
            json.dump(execution, handle, indent=2, sort_keys=True); handle.write("\n")
        with open(args.versions, "w", encoding="utf-8") as handle:
            handle.write(f'"TRACK_AGGREGATE":\n    python: "{sys.version.split()[0]}"\n')
        manifest = {"schema_version": "1.0", "type": "track_aggregate", "tracks": len(rows), "references": references, "artifacts": {"tracks": {"path": "tracks", "available": True}, "track_table": {"path": "tracks.tsv", "sha256": sha256(output / "tracks.tsv")}}, "execution": execution, "status": "complete" if rows else "complete_empty"}
        with open(args.manifest, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2, sort_keys=True); handle.write("\n")
        with open(output / "manifest.json", "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2, sort_keys=True); handle.write("\n")
    except (ValueError, KeyError, json.JSONDecodeError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr); return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
