#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from integration.workflow.terminal import build_integrative_run_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the Integrative terminal run manifest")
    for name in ("rna_manifest", "chip_manifest", "validation_dir", "rna_evidence_dir", "chip_evidence_dir", "harmonization_dir", "integration_dir", "interpretation_dir", "functional_dir", "visualization_dir", "report_dir"):
        parser.add_argument("--" + name.replace("_", "-"), required=True, type=Path)
    parser.add_argument("--run-base64", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    run = json.loads(base64.b64decode(args.run_base64).decode("utf-8"))
    build_integrative_run_manifest(args.rna_manifest, args.chip_manifest, args.validation_dir, args.rna_evidence_dir, args.chip_evidence_dir, args.harmonization_dir, args.integration_dir, args.interpretation_dir, args.functional_dir, args.visualization_dir, args.report_dir, run, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
