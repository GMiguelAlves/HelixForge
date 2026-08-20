#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from integration.molecular import build_master_evidence  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Master Molecular Evidence Table v1")
    parser.add_argument("--rna-evidence-dir", required=True, type=Path)
    parser.add_argument("--chip-evidence-dir", required=True, type=Path)
    parser.add_argument("--harmonization-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    build_master_evidence(args.rna_evidence_dir, args.chip_evidence_dir, args.harmonization_dir, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
