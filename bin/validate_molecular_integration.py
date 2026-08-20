#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from integration.validation import validate_harmonization, validate_integration  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    document = json.loads(args.manifest.read_text(encoding="utf-8"))
    validator = validate_harmonization if document.get("type") == "cross_assay_harmonization" else validate_integration
    errors = validator(document, args.manifest.parent)
    for error in errors:
        print(error, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
