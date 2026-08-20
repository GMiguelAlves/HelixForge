#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from integration.evidence.io import load_bindings, read_json  # noqa: E402
from integration.evidence.provider import build_evidence  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Standardized Evidence Model v1 datasets")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--bindings", required=True, type=Path)
    parser.add_argument("--declared-artifact", action="append", default=[], type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--validation-report", required=True, type=Path)
    args = parser.parse_args()
    try:
        bindings = load_bindings(args.bindings, args.declared_artifact)
        document = build_evidence(read_json(args.manifest), bindings, args.output_dir)
        report = {"schema_version": "1.0", "type": "evidence_validation", "manifest_id": document["id"], "schema": "valid", "semantic": "valid", "filesystem": "valid", "status": "complete"}
        args.validation_report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except Exception as error:
        args.validation_report.write_text(json.dumps({"schema_version": "1.0", "type": "evidence_validation", "status": "invalid", "error": str(error)}, indent=2) + "\n", encoding="utf-8")
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
