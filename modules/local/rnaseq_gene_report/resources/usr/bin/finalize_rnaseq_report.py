#!/usr/bin/env python3
"""Add provenance and a manifest to an RNA-seq report result tree."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", required=True)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--execution", type=Path, required=True)
    parser.add_argument("--versions", type=Path, required=True)
    parser.add_argument("--session-info", type=Path, required=True)
    parser.add_argument("--container", required=True)
    parser.add_argument("--git-commit", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--cpus", type=int, required=True)
    parser.add_argument("--memory-bytes", type=int, required=True)
    parser.add_argument("--task-time", required=True)
    parser.add_argument("--started-epoch", type=int, required=True)
    parser.add_argument("--ended-epoch", type=int, required=True)
    args = parser.parse_args()

    context = load(args.context)
    required = [args.results / "gene_set_report.html", args.results / "tables", args.results / "plots"]
    if any(not path.exists() for path in required):
        raise ValueError("Report provider did not produce HTML, tables and plots.")
    files = []
    for path in sorted(item for item in args.results.rglob("*") if item.is_file()):
        relative = path.relative_to(args.results).as_posix()
        files.append({"path": relative, "sha256": sha256(path), "bytes": path.stat().st_size})

    execution = {
        "schema_version": "1.0",
        "id": args.id,
        "process": "RNASEQ_GENE_REPORT",
        "provider": args.provider,
        "status": "complete",
        "cpus": args.cpus,
        "memory_bytes": args.memory_bytes,
        "time": args.task_time,
        "container": args.container,
        "git_commit": args.git_commit,
        "profile": args.profile,
        "started_epoch": args.started_epoch,
        "ended_epoch": args.ended_epoch,
        "elapsed_seconds": args.ended_epoch - args.started_epoch,
    }
    args.execution.write_text(json.dumps(execution, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.versions.write_text(
        f'"RNASEQ_GENE_REPORT":\n    provider: "{args.provider}"\n    container: "{args.container}"\n',
        encoding="utf-8",
    )
    manifest = {
        "schema_version": "1.0",
        "type": "rnaseq_report",
        "id": args.id,
        "provider": args.provider,
        "status": "complete",
        "parameters": context.get("parameters", {}),
        "sample_count": context.get("sample_count"),
        "gene_count": context.get("gene_count"),
        "query_count": context.get("query_count"),
        "upstream": {
            "import_manifest_sha256": context["inputs"]["import_manifest"]["sha256"],
            "de_manifest_sha256": context["inputs"]["de_manifest"]["sha256"],
        },
        "artifacts": {
            "html": {"path": "gene_set_report.html", "available": True},
            "tables": {"path": "tables", "available": True},
            "plots": {"path": "plots", "available": True},
        },
        "inventory": files,
        "generated_epoch": int(time.time()),
    }
    (args.results / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
