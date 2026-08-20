#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from integration.harmonization import build_harmonization  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Cross-Assay Harmonization v1")
    parser.add_argument("--rna-evidence-dir", required=True, type=Path)
    parser.add_argument("--chip-evidence-dir", required=True, type=Path)
    parser.add_argument("--policy", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    policy = json.loads(args.policy.read_text(encoding="utf-8")) if args.policy else {}
    build_harmonization(args.rna_evidence_dir, args.chip_evidence_dir, args.output_dir, policy)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
