#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import sys
import time


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_manifests(paths):
    documents = {}
    for path in paths:
        with open(path, encoding="utf-8") as handle:
            document = json.load(handle)
        if document.get("type") not in {"consensus", "idr"}:
            raise ValueError(f"{path}: unsupported provider manifest type {document.get('type')!r}")
        identifier = str(document.get("id", ""))
        if not identifier or identifier in documents:
            raise ValueError(f"empty or duplicate provider group id: {identifier!r}")
        if document["type"] == "idr" and document.get("strategy") != "idr":
            raise ValueError(f"{path}: IDR manifest has incompatible strategy")
        if document["type"] == "consensus" and document.get("strategy") not in {"union", "intersection", "replicate_support"}:
            raise ValueError(f"{path}: consensus manifest has incompatible strategy")
        documents[identifier] = (document, path)
    if not documents:
        raise ValueError("no Consensus/IDR provider manifests were supplied")
    return documents


def summarize(documents):
    rows = []
    for identifier in sorted(documents):
        document = documents[identifier][0]
        artifact = document.get("artifacts", {}).get("consolidated_peaks", {"available": False})
        rows.append({
            "group_id": identifier, "dataset": document.get("dataset"),
            "experiment_id": document.get("experiment_id"), "condition": document.get("condition"),
            "treatment": document.get("treatment"), "target": document.get("target"),
            "genome_id": document.get("genome_id"), "peak_type": document.get("peak_type"),
            "caller": document.get("caller"), "caller_version": document.get("caller_version"),
            "strategy": document.get("strategy"), "status": document.get("status"),
            "replicate_mode": document.get("replicate_mode"),
            "replicate_policy": document.get("replicate_policy"),
            "replicate_count": len(document.get("replicates", [])),
            "consolidated_peaks_available": bool(artifact.get("available")),
            "consolidated_peaks_path": artifact.get("path"),
        })
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider-manifest", action="append", required=True)
    parser.add_argument("--summary-json", required=True)
    parser.add_argument("--summary-tsv", required=True)
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
        documents = load_manifests(args.provider_manifest)
        rows = summarize(documents)
        columns = list(rows[0])
        with open(args.summary_tsv, "w", encoding="utf-8") as handle:
            handle.write("\t".join(columns) + "\n")
            for row in rows:
                handle.write("\t".join("" if row[column] is None else str(row[column]).lower() if isinstance(row[column], bool) else str(row[column]) for column in columns) + "\n")
        strategies = sorted({row["strategy"] for row in rows})
        summary = {"schema_version": "1.0", "type": "consensus_idr_summary", "groups": len(rows), "strategies": strategies, "rows": rows, "status": "complete"}
        with open(args.summary_json, "w", encoding="utf-8") as handle:
            json.dump(summary, handle, indent=2, sort_keys=True)
            handle.write("\n")
        ended = int(time.time())
        execution = {
            "schema_version": "1.0", "id": "chipseq.consensus.aggregate", "process": "CONSENSUS_AGGREGATE",
            "cpus": args.cpus, "memory_bytes": args.memory_bytes, "time": args.task_time,
            "nextflow_version": args.nextflow_version,
            "started_epoch": started, "ended_epoch": ended, "elapsed_seconds": ended - started,
        }
        with open(args.execution, "w", encoding="utf-8") as handle:
            json.dump(execution, handle, indent=2, sort_keys=True)
            handle.write("\n")
        with open(args.versions, "w", encoding="utf-8") as handle:
            handle.write(f'"CONSENSUS_AGGREGATE":\n    python: "{sys.version.split()[0]}"\n')
        manifest = {
            "schema_version": "1.0", "type": "consensus_idr", "groups": len(rows),
            "strategies": strategies,
            "provider_manifests": [
                {"group_id": identifier, "path": os.path.basename(path), "sha256": sha256(path),
                 "status": document.get("status")}
                for identifier, (document, path) in sorted(documents.items())
            ],
            "artifacts": {
                "summary": {"path": os.path.basename(args.summary_tsv), "sha256": sha256(args.summary_tsv)},
                "summary_json": {"path": os.path.basename(args.summary_json), "sha256": sha256(args.summary_json)},
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
