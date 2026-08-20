#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from integration.workflow.reporting import build_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the native Integrative report")
    for name in ("input_dir", "rna_evidence_dir", "chip_evidence_dir", "harmonization_dir", "integration_dir", "interpretation_dir", "functional_dir", "visualization_dir", "output_dir"):
        parser.add_argument("--" + name.replace("_", "-"), required=True, type=Path)
    parser.add_argument("--title", default="HelixForge Integrative Report")
    args = parser.parse_args()
    build_report(args.input_dir, args.rna_evidence_dir, args.chip_evidence_dir, args.harmonization_dir, args.integration_dir, args.interpretation_dir, args.functional_dir, args.visualization_dir, args.output_dir, args.title)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
