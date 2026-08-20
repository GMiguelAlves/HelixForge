#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.molecular_integration.test_molecular_integration import legacy_bundles  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    rna, chip = legacy_bundles(args.output)
    print(rna)
    print(chip)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
