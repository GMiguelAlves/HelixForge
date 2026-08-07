#!/usr/bin/env python3
from __future__ import annotations

import argparse
import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("plan")
    args = parser.parse_args()

    plan = pd.read_csv(args.plan, dtype=str, keep_default_na=False)
    print(f"runs={len(plan)}")
    print(f"samples={plan['sample_id'].nunique()}")


if __name__ == "__main__":
    main()
