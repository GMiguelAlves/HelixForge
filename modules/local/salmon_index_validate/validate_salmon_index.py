#!/usr/bin/env python3
"""Validate the identity and integrity of a reusable Salmon index."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import time
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def index_inventory(index: Path) -> tuple[list[Path], int]:
    files = sorted(
        (path for path in index.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(index).as_posix(),
    )
    return files, sum(path.stat().st_size for path in files)


def canonical_index_sha256(index: Path, files: list[Path] | None = None) -> str:
    """Match the checksum emitted by SALMON_INDEX independent of its location."""
    files = files if files is not None else index_inventory(index)[0]
    digest = hashlib.sha256()
    for path in files:
        relative = path.relative_to(index).as_posix()
        line = f"{sha256_file(path)}  salmon_index/{relative}\n"
        digest.update(line.encode("utf-8"))
    return digest.hexdigest()


def nested_value(document: dict[str, Any], *paths: tuple[str, ...]) -> Any:
    for keys in paths:
        current: Any = document
        for key in keys:
            if not isinstance(current, dict) or key not in current:
                break
            current = current[key]
        else:
            return current
    return None


def validate(index: Path, transcriptome: Path, manifest_path: Path, expected_kmer: int) -> dict[str, Any]:
    if not index.is_dir():
        raise ValueError(f"prebuilt Salmon index is not a directory: {index}")
    if not transcriptome.is_file():
        raise ValueError(f"transcriptome is not a file: {transcriptome}")

    required_files = ("versionInfo.json", "info.json")
    missing = [name for name in required_files if not (index / name).is_file()]
    if missing:
        raise ValueError(f"prebuilt Salmon index is incomplete; missing: {', '.join(missing)}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    version_info = json.loads((index / "versionInfo.json").read_text(encoding="utf-8"))
    info = json.loads((index / "info.json").read_text(encoding="utf-8"))

    manifest_transcriptome_sha = nested_value(
        manifest, ("transcriptome_sha256",), ("transcriptome", "sha256")
    )
    manifest_salmon_version = nested_value(
        manifest, ("salmon_version",), ("versions", "salmon")
    )
    manifest_kmer = nested_value(
        manifest, ("kmer_size",), ("parameters", "kmer_size")
    )
    manifest_index_version = nested_value(manifest, ("index_version",))
    manifest_index_sha = nested_value(
        manifest, ("index_sha256",), ("sha256",), ("composite_sha256",)
    )

    required_manifest = {
        "transcriptome_sha256": manifest_transcriptome_sha,
        "salmon_version": manifest_salmon_version,
        "kmer_size": manifest_kmer,
        "index_version": manifest_index_version,
        "index_sha256": manifest_index_sha,
    }
    absent = [name for name, value in required_manifest.items() if value in (None, "")]
    if absent:
        raise ValueError(f"prebuilt-index manifest lacks required identity fields: {', '.join(absent)}")

    transcriptome_sha = sha256_file(transcriptome)
    files, size_bytes = index_inventory(index)
    index_sha = canonical_index_sha256(index, files)
    observed_salmon_version = str(version_info.get("salmonVersion", ""))
    observed_index_version = version_info.get("indexVersion")
    observed_kmer = version_info.get("auxKmerLength", info.get("k"))

    checks = {
        "transcriptome_sha256": transcriptome_sha == str(manifest_transcriptome_sha),
        "index_sha256": index_sha == str(manifest_index_sha),
        "salmon_version": observed_salmon_version == str(manifest_salmon_version),
        "index_version": observed_index_version == int(manifest_index_version),
        "manifest_kmer_size": observed_kmer == int(manifest_kmer),
        "requested_kmer_size": observed_kmer == expected_kmer,
    }
    if manifest.get("file_count") is not None:
        checks["file_count"] = len(files) == int(manifest["file_count"])
    if manifest.get("size_bytes") is not None:
        checks["size_bytes"] = size_bytes == int(manifest["size_bytes"])

    failed = [name for name, passed in checks.items() if not passed]
    result = {
        "schema_version": "1.0",
        "type": "salmon_prebuilt_index_validation",
        "status": "PASS" if not failed else "FAIL",
        "checks": checks,
        "observed": {
            "transcriptome_sha256": transcriptome_sha,
            "index_sha256": index_sha,
            "salmon_version": observed_salmon_version,
            "index_version": observed_index_version,
            "kmer_size": observed_kmer,
            "file_count": len(files),
            "size_bytes": size_bytes,
        },
    }
    if failed:
        raise ValueError("prebuilt Salmon index validation failed: " + ", ".join(failed))
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--transcriptome", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--expected-kmer-size", type=int, required=True)
    parser.add_argument("--id", required=True)
    parser.add_argument("--validation-json", type=Path, required=True)
    parser.add_argument("--validation-log", type=Path, required=True)
    parser.add_argument("--versions-yml", type=Path, required=True)
    parser.add_argument("--execution-json", type=Path, required=True)
    parser.add_argument("--output-manifest", type=Path, required=True)
    parser.add_argument("--status-json", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    started = int(time.time())
    try:
        result = validate(args.index, args.transcriptome, args.manifest, args.expected_kmer_size)
    except Exception as error:
        args.validation_log.write_text(f"FAIL: {error}\n", encoding="utf-8")
        raise

    ended = int(time.time())
    result["id"] = args.id
    args.validation_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.validation_log.write_text(
        "PASS: prebuilt Salmon index identity and integrity validated; no index was built or modified.\n",
        encoding="utf-8",
    )
    args.versions_yml.write_text(
        f'"SALMON_INDEX_VALIDATE":\n    python: "{platform.python_version()}"\n'
        f'    salmon_index: "{result["observed"]["salmon_version"]}"\n',
        encoding="utf-8",
    )
    execution = {
        "id": args.id,
        "process": "SALMON_INDEX_VALIDATE",
        "status": "complete",
        "source": "prebuilt",
        "started_epoch": started,
        "ended_epoch": ended,
        "elapsed_seconds": ended - started,
        "validation": result["checks"],
    }
    args.execution_json.write_text(json.dumps(execution, sort_keys=True) + "\n", encoding="utf-8")
    output_manifest = {
        "schema_version": "1.0",
        "type": "transcriptome_index",
        "id": args.id,
        "status": "complete",
        "quantifier": "salmon",
        "source": "prebuilt",
        "sha256": result["observed"]["index_sha256"],
        "transcriptome_sha256": result["observed"]["transcriptome_sha256"],
        "parameters": {"kmer_size": result["observed"]["kmer_size"]},
        "versions": {
            "salmon": result["observed"]["salmon_version"],
            "index": result["observed"]["index_version"],
        },
    }
    args.output_manifest.write_text(json.dumps(output_manifest, sort_keys=True) + "\n", encoding="utf-8")
    args.status_json.write_text(
        json.dumps({"id": args.id, "process": "SALMON_INDEX_VALIDATE", "status": "complete"}) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
