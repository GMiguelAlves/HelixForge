#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from integration.workflow.functional import build_functional_analysis


def main() -> int:
    parser = argparse.ArgumentParser(description="Run downstream Integrative functional analysis")
    parser.add_argument("--interpretation-dir", required=True, type=Path)
    parser.add_argument("--annotation", required=True, type=Path)
    parser.add_argument("--top-n", type=int, default=100)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    build_functional_analysis(args.interpretation_dir, args.annotation, args.top_n, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
