#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from integration.workflow.preflight import prepare_inputs


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and materialize portable Integrative inputs")
    parser.add_argument("--rna-manifest", required=True, type=Path)
    parser.add_argument("--rna-artifacts", required=True, type=Path)
    parser.add_argument("--chip-manifest", required=True, type=Path)
    parser.add_argument("--chip-artifacts", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    prepare_inputs(args.rna_manifest, args.rna_artifacts, args.chip_manifest, args.chip_artifacts, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
