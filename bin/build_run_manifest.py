#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path

from integration_contract import build_run_manifest
from validate_integration_manifest import jsonschema_errors


def decode(value: str):
    return json.loads(base64.b64decode(value).decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--assay", required=True, choices=("rnaseq", "chipseq"))
    parser.add_argument("--run-base64", required=True)
    parser.add_argument("--metadata", required=True, type=Path)
    parser.add_argument("--reference-manifest", required=True, type=Path)
    parser.add_argument("--source-manifest", action="append", default=[], type=Path)
    parser.add_argument("--artifact", action="append", default=[], type=Path)
    parser.add_argument("--artifact-specs-base64", required=True)
    parser.add_argument("--contrast-spec", type=Path)
    parser.add_argument("--status", default="complete", choices=("complete", "complete_empty", "stub"))
    parser.add_argument("--skip-json-schema", action="store_true", help="Reserved for dependency-free Nextflow stub runs")
    parser.add_argument("--schema-root", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--validation-report", required=True, type=Path)
    args = parser.parse_args()
    document = build_run_manifest(
        assay=args.assay, run=decode(args.run_base64), metadata=args.metadata,
        reference_manifest=args.reference_manifest, source_manifests=args.source_manifest,
        artifacts=args.artifact, artifact_specs=decode(args.artifact_specs_base64),
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
