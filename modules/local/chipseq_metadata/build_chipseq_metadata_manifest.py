#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metadata", required=True, type=Path)
    parser.add_argument("--validation", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args()

    with args.metadata.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    if not rows:
        raise ValueError("validated ChIP-seq metadata is empty")
    datasets = sorted({row["dataset"] for row in rows})
    genome_ids = sorted({row["genome_id"] for row in rows})
    document = {
        "schema_version": "1.0",
        "type": "chipseq_metadata",
        "id": "chipseq.metadata",
        "datasets": datasets,
        "genome_ids": genome_ids,
        "rows": rows,
        "artifacts": {
            "metadata": {"path": args.metadata.name, "sha256": sha256(args.metadata)},
            "validation": {"path": args.validation.name, "sha256": sha256(args.validation)},
        },
        "status": "complete",
    }
    if len(datasets) == 1:
        document["dataset"] = datasets[0]
    if len(genome_ids) == 1:
        document["genome_id"] = genome_ids[0]
        document["build"] = genome_ids[0]
    args.manifest.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
