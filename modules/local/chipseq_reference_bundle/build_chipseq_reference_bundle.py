#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def artifact(path: Path) -> dict:
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f"reference artifact is missing or empty: {path}")
    return {"available": True, "path": path.name, "sha256": sha256(path)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference-id", required=True)
    parser.add_argument("--genome-id", required=True)
    parser.add_argument("--build", required=True)
    parser.add_argument("--organism", default="")
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--annotation", required=True, type=Path)
    parser.add_argument("--blacklist", type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--validation", required=True, type=Path)
    args = parser.parse_args()

    artifacts = {
        "reference": artifact(args.reference),
        "annotation": artifact(args.annotation),
        "blacklist": {"available": False},
    }
    if args.blacklist:
        artifacts["blacklist"] = artifact(args.blacklist)
    manifest = {
        "schema_version": "1.0", "type": "reference_bundle", "id": args.reference_id,
        "genome_id": args.genome_id, "build": args.build, "organism": args.organism,
        "artifacts": artifacts, "status": "complete",
    }
    args.manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.validation.write_text(json.dumps({"schema_version": "1.0", "status": "valid", "artifacts": artifacts}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
