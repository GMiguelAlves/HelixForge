#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from integration.interpretation import build_candidate_scores  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Build HelixForge Candidate Score v1")
    parser.add_argument("--integration-dir", required=True, type=Path)
    parser.add_argument("--classification-dir", required=True, type=Path)
    parser.add_argument("--policy", required=True, type=Path)
    parser.add_argument("--context", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    build_candidate_scores(args.integration_dir, args.classification_dir, args.policy, args.context, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
