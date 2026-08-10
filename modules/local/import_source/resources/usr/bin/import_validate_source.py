#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--artifact", required=True, type=Path)
    parser.add_argument("--role", required=True)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--source-name", required=True)
    parser.add_argument("--target-root", default="")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    document = json.loads(args.manifest.read_text(encoding="utf-8"))
    observed_provider = document.get("quantifier") or document.get("aligner")
    if observed_provider != args.provider:
        raise ValueError(f"provider mismatch: expected {args.provider}, observed {observed_provider}")
    artifact_spec = document.get("artifacts", {}).get(args.role)
    if not isinstance(artifact_spec, dict):
        raise ValueError(f"manifest does not expose artifact role: {args.role}")

    observed_sha = sha256(args.artifact)
    expected_sha = artifact_spec.get("sha256", "")
    if expected_sha and expected_sha != observed_sha:
        raise ValueError(f"checksum mismatch for {args.role}: {expected_sha} != {observed_sha}")

    expected_name = Path(artifact_spec.get("path", args.artifact.name)).name
    if expected_name != args.artifact.name:
        raise ValueError(f"artifact name mismatch: {expected_name} != {args.artifact.name}")

    compatibility_path = artifact_spec.get("compatibility_path", "")
    if not compatibility_path and args.target_root:
        compatibility_path = str(Path(args.target_root) / artifact_spec["path"])

    args.output.mkdir(parents=True, exist_ok=False)
    # Preserve content, not host timestamps/ownership. copy2() calls copystat(),
    # which is not portable to every Docker/Apptainer bind mount.
    shutil.copyfile(args.artifact, args.output / "artifact")
    shutil.copyfile(args.manifest, args.output / "manifest.json")

    source = {
        "schema_version": "1.0",
        "type": "import_source",
        "id": args.source_name,
        "status": "complete",
        "source_name": args.source_name,
        "provider": args.provider,
        "role": args.role,
        "dataset": document.get("dataset", ""),
        "sample_id": document.get("sample_id", ""),
        "provider_id": document.get("id", ""),
        "provider_manifest_sha256": sha256(args.manifest),
        "artifact_sha256": observed_sha,
        "compatibility_path": compatibility_path,
    }
    (args.output / "source.json").write_text(
        json.dumps(source, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(source, sort_keys=True))


if __name__ == "__main__":
    main()
