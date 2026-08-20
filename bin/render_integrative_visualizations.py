#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from integration.workflow.visualization import build_visualizations


def main() -> int:
    parser = argparse.ArgumentParser(description="Render Integrative figures from structured products")
    parser.add_argument("--interpretation-dir", required=True, type=Path)
    parser.add_argument("--functional-dir", required=True, type=Path)
    parser.add_argument("--panel-count", type=int, default=5)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    build_visualizations(args.interpretation_dir, args.functional_dir, args.output_dir, args.panel_count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
