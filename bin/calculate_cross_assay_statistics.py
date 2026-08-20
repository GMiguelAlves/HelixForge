#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from integration.interpretation import build_cross_assay_statistics  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Build cross-assay statistics and Interpretation Manifest v1")
    parser.add_argument("--integration-dir", required=True, type=Path)
    parser.add_argument("--classification-dir", required=True, type=Path)
    parser.add_argument("--scoring-dir", required=True, type=Path)
    parser.add_argument("--policy", required=True, type=Path)
    parser.add_argument("--mark-roles", required=True, type=Path)
    parser.add_argument("--context", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    build_cross_assay_statistics(args.integration_dir, args.classification_dir, args.scoring_dir, args.policy, args.mark_roles, args.context, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
