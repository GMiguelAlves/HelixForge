#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from integration.interpretation import build_regulatory_interpretation  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Regulatory Interpretation Model v1")
    parser.add_argument("--integration-dir", required=True, type=Path)
    parser.add_argument("--policy", required=True, type=Path)
    parser.add_argument("--mark-roles", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    build_regulatory_interpretation(args.integration_dir, args.policy, args.mark_roles, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
