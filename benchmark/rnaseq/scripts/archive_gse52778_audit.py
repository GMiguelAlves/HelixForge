#!/usr/bin/env python3
"""Create a compact, checksummed GSE52778 audit ZIP without large raw/work data."""

from __future__ import annotations

import argparse
import hashlib
import io
import os
import zipfile
from pathlib import Path


SMALL_PIPELINE_SUFFIXES = {
    ".csv", ".html", ".json", ".png", ".tsv", ".txt", ".yaml", ".yml"
}


def files_under(root: Path):
    if not root.exists():
        return
    for path in sorted(root.rglob("*")):
        if path.is_file() and not path.is_symlink():
            yield path


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark-root", required=True, type=Path)
    parser.add_argument("--readme", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    root = args.benchmark_root.resolve(strict=True)
    readme = args.readme.resolve(strict=True)
    output = args.output
    if output.exists() or output.with_suffix(output.suffix + ".partial").exists():
        raise FileExistsError(f"refusing to overwrite audit archive: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)

    case = root / "cases" / "helixforge-full-run1"
    independent = root / "cases" / "independent-reference"
    selections: list[tuple[Path, str]] = []

    def include_tree(source: Path, prefix: str) -> None:
        for path in files_under(source):
            selections.append((path, f"{prefix}/{path.relative_to(source).as_posix()}"))

    for directory in ("metadata", "provenance", "audit", "logs"):
        include_tree(root / directory, directory)
    include_tree(root / "download" / "manifests", "download_manifests")
    include_tree(case / "results", "helixforge_results")
    include_tree(case / "validation", "validation")
    include_tree(case / "logs", "helixforge_logs")
    include_tree(case / "report-hotfix-recovery" / "logs", "report_recovery/logs")
    include_tree(case / "terminal-manifest-recovery" / "logs", "manifest_recovery/logs")
    for identity, arcname in (
        (case / "report-hotfix-recovery" / "recovery_identity.json", "report_recovery/recovery_identity.json"),
        (case / "terminal-manifest-recovery" / "recovery_identity.json", "manifest_recovery/recovery_identity.json"),
    ):
        if identity.is_file():
            selections.append((identity, arcname))
    include_tree(independent, "independent_reference")

    for area in (
        case / "pipeline" / "060-deg-analysis",
        case / "pipeline" / "090-search-gene",
    ):
        for path in files_under(area):
            if path.suffix.lower() in SMALL_PIPELINE_SUFFIXES:
                selections.append((path, f"pipeline_outputs/{path.relative_to(case / 'pipeline').as_posix()}"))

    for path in files_under(root / "reference"):
        if path.suffix.lower() in {".json", ".tsv", ".txt", ".yaml", ".yml"} and path.stat().st_size <= 10_000_000:
            selections.append((path, f"reference_metadata/{path.relative_to(root / 'reference').as_posix()}"))

    unique: dict[str, Path] = {}
    for path, arcname in selections:
        unique.setdefault(arcname, path)

    partial = output.with_suffix(output.suffix + ".partial")
    manifest = ["archive_path\tsize_bytes\tsha256"]
    try:
        with zipfile.ZipFile(partial, "w", zipfile.ZIP_DEFLATED, allowZip64=True, compresslevel=6) as archive:
            archive.write(readme, "README_PT.md")
            manifest.append(f"README_PT.md\t{readme.stat().st_size}\t{digest(readme)}")
            for arcname, path in sorted(unique.items()):
                archive.write(path, arcname)
                manifest.append(f"{arcname}\t{path.stat().st_size}\t{digest(path)}")
            payload = ("\n".join(manifest) + "\n").encode("utf-8")
            archive.writestr("ARQUIVOS_SHA256.tsv", payload)
        os.replace(partial, output)
    except Exception:
        partial.unlink(missing_ok=True)
        raise

    archive_hash = digest(output)
    output.with_suffix(output.suffix + ".sha256").write_text(
        f"{archive_hash}  {output.name}\n", encoding="utf-8"
    )
    print(f"archive={output}")
    print(f"files={len(unique) + 2}")
    print(f"bytes={output.stat().st_size}")
    print(f"sha256={archive_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

