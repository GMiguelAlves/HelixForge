#!/usr/bin/env python3
"""Relocate the frozen 10B fixture and validate both manifest entry roots."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_tsv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def archived_checksums(path: Path) -> dict[str, str]:
    with zipfile.ZipFile(path) as archive:
        lines = archive.read("execution/SHA256SUMS").decode("utf-8").splitlines()
    return {relative: checksum for checksum, relative in (line.split("  ", 1) for line in lines)}


def manifest_rows(repo: Path, route: str, root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    sys.path.insert(0, str(repo / "bin"))
    from integration_contract import compatibility_errors, filesystem_errors, schema_contract_errors, semantic_errors
    from validate_integration_manifest import jsonschema_errors

    rows: list[dict[str, Any]] = []
    failures: list[str] = []
    documents = {
        "rnaseq": load(root / "rna/rnaseq_run_manifest.json"),
        "chipseq": load(root / "chip/chipseq_run_manifest.json"),
    }
    compatible = compatibility_errors(documents["rnaseq"], documents["chipseq"])
    schema_root = repo / "schemas" / "integration"
    for assay, filename in (("rnaseq", "rna/rnaseq_run_manifest.json"), ("chipseq", "chip/chipseq_run_manifest.json")):
        manifest = root / filename
        document = documents[assay]
        schema = jsonschema_errors(document, schema_root)
        semantic = schema_contract_errors(document) + semantic_errors(document)
        filesystem = filesystem_errors(document, manifest)
        portability = []
        for artifact in document.get("artifacts", []):
            location = artifact.get("location") or {}
            raw = str(location.get("path") or "")
            if location.get("kind") != "manifest_relative" or Path(raw).is_absolute():
                portability.append(str(artifact.get("artifact_id")))
        statuses = {
            "schema": "PASS" if not schema else "FAIL",
            "semantic": "PASS" if not semantic else "FAIL",
            "filesystem": "PASS" if not filesystem else "FAIL",
            "portability": "PASS" if not portability else "FAIL",
            "reference": "PASS" if not compatible else "FAIL",
        }
        failures.extend(f"{route}/{assay}/{key}: {value}" for key, value in statuses.items() if value != "PASS")
        failures.extend(schema + semantic + filesystem + compatible)
        if portability:
            failures.append(f"{route}/{assay}: non-portable artifacts: {','.join(portability)}")
        rows.append({
            "route": route,
            "assay": assay,
            "manifest": Path(filename).name,
            "schema_version": document.get("schema_version"),
            "manifest_sha256": sha256(manifest),
            "schema_validation": statuses["schema"],
            "semantic_validation": statuses["semantic"],
            "filesystem_validation": statuses["filesystem"],
            "reference_compatibility": statuses["reference"],
            "portable_locations": statuses["portability"],
            "artifacts": len(document.get("artifacts", [])),
        })
    return rows, failures


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--direct-root", type=Path, required=True)
    parser.add_argument("--reentry-root", type=Path, required=True)
    parser.add_argument("--baseline-audit", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo_root.resolve()
    direct = args.direct_root.resolve()
    reentry = args.reentry_root.resolve()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if direct == reentry or direct in reentry.parents or reentry in direct.parents:
        raise ValueError("direct and re-entry roots must be independent sibling trees")

    expected = archived_checksums(args.baseline_audit.resolve())
    identity_rows: list[dict[str, Any]] = []
    failures: list[str] = []
    for relative, expected_sha in sorted(expected.items()):
        if not (relative.startswith(("rna/", "chip/")) or relative in {
            "functional_annotation.tsv", "harmonization_policy.json", "prioritization_context.tsv"
        }):
            continue
        source = direct / relative
        observed = sha256(source) if source.is_file() else "MISSING"
        status = "PASS" if observed == expected_sha else "FAIL"
        identity_rows.append({"artifact": relative, "baseline_sha256": expected_sha, "direct_sha256": observed, "reentry_sha256": "", "status": status})
        if status != "PASS":
            failures.append(f"10B input identity differs: {relative}")

    for name in ("rna", "chip"):
        shutil.copytree(direct / name, reentry / name, copy_function=shutil.copy2)
    for name in ("functional_annotation.tsv", "harmonization_policy.json", "prioritization_context.tsv"):
        shutil.copy2(direct / name, reentry / name)

    for row in identity_rows:
        copied = reentry / row["artifact"]
        row["reentry_sha256"] = sha256(copied) if copied.is_file() else "MISSING"
        if row["reentry_sha256"] != row["direct_sha256"]:
            row["status"] = "FAIL"
            failures.append(f"relocated artifact identity differs: {row['artifact']}")

    rna_a = direct / "rna/rnaseq_run_manifest.json"
    chip_a = direct / "chip/chipseq_run_manifest.json"
    validation_rows: list[dict[str, Any]] = []
    for route, root in (("A", direct), ("B", reentry)):
        rows, route_failures = manifest_rows(repo, route, root)
        validation_rows.extend(rows)
        failures.extend(route_failures)

    # Remove duplicate diagnostic strings introduced by the assay-specific pass.
    failures = sorted(set(failures))
    write_tsv(output / "manifest_validation.tsv", validation_rows)
    write_tsv(output / "input_artifact_identity.tsv", identity_rows)
    summary = {
        "schema_version": "1.0",
        "type": "integrative_reentry_fixture_validation",
        "status": "PASS" if not failures else "FAIL",
        "baseline_10b_input_identity": "PASS" if all(row["status"] == "PASS" for row in identity_rows) else "FAIL",
        "isolated_roots": direct != reentry and direct not in reentry.parents and reentry not in direct.parents,
        "direct_root": "direct_bundle",
        "reentry_root": "relocated_bundle",
        "rna_manifest_sha256": sha256(rna_a),
        "chip_manifest_sha256": sha256(chip_a),
        "failures": failures,
    }
    (output / "setup_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": summary["status"], "artifacts": len(identity_rows), "failures": failures}, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
