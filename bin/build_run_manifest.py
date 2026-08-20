#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import copy
import json
import shutil
from pathlib import Path

from integration_contract import build_run_manifest
from validate_integration_manifest import jsonschema_errors


PORTABLE_INTEGRATION_TYPES = {
    "gene_counts", "gene_abundance", "normalized_counts",
    "differential_expression", "differential_expression_summary",
    "peak_set", "consensus_peaks", "idr_peaks",
    "differential_binding", "peak_gene_annotation",
}


def decode(value: str):
    return json.loads(base64.b64decode(value).decode("utf-8"))


def portable_inputs(specs, artifacts, output_dir: Path | None):
    copied_specs = copy.deepcopy(specs)
    if output_dir is None:
        return copied_specs
    output_dir.mkdir(parents=True, exist_ok=True)
    for spec, source in zip(copied_specs, artifacts):
        if spec.get("artifact_type") not in PORTABLE_INTEGRATION_TYPES:
            continue
        safe_id = "".join(char if char.isalnum() or char in "._-" else "_" for char in spec["artifact_id"]).strip("_")
        target_root = output_dir / safe_id
        target_root.mkdir(parents=True, exist_ok=True)
        target = target_root / source.name
        if source.is_dir():
            shutil.copytree(source, target, dirs_exist_ok=True)
        else:
            shutil.copy2(source, target)
        spec["location"] = {
            "kind": "manifest_relative",
            "path": target.relative_to(output_dir.parent).as_posix(),
            "base_path": None,
            "producer_manifest_id": None,
        }
    return copied_specs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--assay", required=True, choices=("rnaseq", "chipseq"))
    parser.add_argument("--run-base64", required=True)
    parser.add_argument("--metadata", required=True, type=Path)
    parser.add_argument("--reference-manifest", required=True, type=Path)
    parser.add_argument("--source-manifest", action="append", default=[], type=Path)
    parser.add_argument("--artifact", action="append", default=[], type=Path)
    parser.add_argument("--artifact-specs-base64", required=True)
    parser.add_argument("--portable-integration-dir", type=Path)
    parser.add_argument("--contrast-spec", type=Path)
    parser.add_argument("--status", default="complete", choices=("complete", "complete_empty", "stub"))
    parser.add_argument("--skip-json-schema", action="store_true", help="Reserved for dependency-free Nextflow stub runs")
    parser.add_argument("--schema-root", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--validation-report", required=True, type=Path)
    args = parser.parse_args()
    artifact_specs = portable_inputs(decode(args.artifact_specs_base64), args.artifact, args.portable_integration_dir)
    document = build_run_manifest(
        assay=args.assay, run=decode(args.run_base64), metadata=args.metadata,
        reference_manifest=args.reference_manifest, source_manifests=args.source_manifest,
        artifacts=args.artifact, artifact_specs=artifact_specs,
        contrast_spec=args.contrast_spec, status=args.status,
    )
    schema_status = "skipped_stub" if args.skip_json_schema else "valid"
    if not args.skip_json_schema:
        schema_root = args.schema_root or Path(__file__).resolve().parents[1] / "schemas" / "integration"
        errors = jsonschema_errors(document, schema_root)
        if errors:
            raise ValueError("invalid Integration API JSON Schema: " + "; ".join(errors))
    args.output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.validation_report.write_text(json.dumps({
        "schema_version": "1.0", "type": "integration_manifest_validation",
        "manifest_id": document["id"], "schema": schema_status, "semantic": "valid",
        "filesystem": "tracked_inputs_verified", "status": "complete",
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
