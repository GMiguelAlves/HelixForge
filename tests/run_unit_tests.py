#!/usr/bin/env python3

import sys
import unittest
from pathlib import Path


def main():
    tests_dir = Path(__file__).resolve().parent
    suite = unittest.defaultTestLoader.discover(
        start_dir=str(tests_dir),
        pattern="test_*.py",
        top_level_dir=str(tests_dir.parent),
    )
    count = suite.countTestCases()
    if count == 0:
        print("ERROR: unittest discovery found zero tests", file=sys.stderr)
        return 2
    print(f"Discovered {count} tests")
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
