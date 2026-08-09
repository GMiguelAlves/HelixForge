#!/usr/bin/env python3

import argparse
import json
from pathlib import Path


def split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


parser = argparse.ArgumentParser()
parser.add_argument("--analysis-id", required=True)
parser.add_argument("--scope", required=True)
parser.add_argument("--correction", required=True)
parser.add_argument("--target-dir", required=True)
parser.add_argument("--test-variables", required=True)
parser.add_argument("--design-covariates", default="")
parser.add_argument("--output", required=True, type=Path)
args = parser.parse_args()

document = {
    "schema_version": "1.0",
    "analysis_id": args.analysis_id,
    "scope": args.scope,
    "correction": args.correction,
    "provider": "deseq2",
    "test": "wald",
    "target_dir": args.target_dir,
    "test_variables": split_csv(args.test_variables),
    "design_covariates": split_csv(args.design_covariates),
    "contrasts": [],
    "parameters": {
        "alpha": 0.05,
        "lfc_threshold": 1,
        "min_replicates": 2,
        "min_total_count": 10,
    },
}
args.output.write_text(json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
