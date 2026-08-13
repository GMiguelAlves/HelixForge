#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path


TYPE_COMPONENT = {
    "metadata": "metadata", "chipseq_metadata": "metadata",
    "reference": "reference", "reference_bundle": "reference",
    "alignment": "alignment", "bam_aligned": "alignment",
    "bam_final": "bam", "peak_calling": "peak",
    "peak_qc": "peak_qc", "peak_qc_summary": "peak_qc",
    "consensus_idr": "consensus_idr", "consensus_idr_summary": "consensus_idr", "idr": "consensus_idr",
    "differential_binding": "differential_binding",
    "peak_annotation": "annotation", "peak_annotation_aggregate": "annotation",
    "track_generation": "tracks", "track_aggregate": "tracks",
}
REQUIRED = [
    "metadata", "reference", "alignment", "bam", "peak", "peak_qc",
    "consensus_idr", "differential_binding", "annotation", "tracks",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def declared_hashes(value) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        digest = value.get("sha256")
        if isinstance(digest, str) and len(digest) == 64:
            found.add(digest)
        for child in value.values():
            found.update(declared_hashes(child))
    elif isinstance(value, list):
        for child in value:
            found.update(declared_hashes(child))
    return found


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--meta-base64", required=True)
    parser.add_argument("--manifest", action="append", default=[], type=Path)
    parser.add_argument("--artifact", action="append", default=[], type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    meta = json.loads(base64.b64decode(args.meta_base64).decode("utf-8"))
    for field in ("project_id", "dataset", "genome_id", "build"):
        if not str(meta.get(field, "")).strip():
            raise ValueError(f"full report metadata requires {field}")

    artifacts = {sha256(path): path for path in args.artifact}
    entries = []
    detected = set()
    identities = set()
    for path in args.manifest:
        document = json.loads(path.read_text(encoding="utf-8"))
        manifest_type = document.get("type")
        component = TYPE_COMPONENT.get(manifest_type)
        if not component:
            raise ValueError(f"unsupported full-report manifest type {manifest_type!r}: {path}")
        identity = (manifest_type, document.get("id"))
        if identity in identities:
            raise ValueError(f"duplicate full-report manifest identity: {identity}")
        identities.add(identity)
        detected.add(component)
        declared = declared_hashes(document)
        entries.append({
            "component": component,
            "manifest": str(path),
            "artifacts": [str(artifact) for digest, artifact in artifacts.items() if digest in declared],
        })
    missing = sorted(set(REQUIRED) - detected)
    if missing:
        raise ValueError("full report is missing required components: " + ", ".join(missing))
    undeclared = sorted(str(path) for digest, path in artifacts.items() if not any(digest in declared_hashes(json.loads(manifest.read_text(encoding="utf-8"))) for manifest in args.manifest))
    if undeclared:
        raise ValueError("semantic artifacts are not checksum-declared: " + ", ".join(undeclared))

    inventory = {
        "schema_version": "1.0", "type": "chipseq_report_input",
        "project": {field: meta[field] for field in ("project_id", "dataset", "genome_id", "build")},
        "required_components": REQUIRED, "components": entries,
    }
    args.output.write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Prepared full report input with {len(entries)} manifests and {len(artifacts)} semantic artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
