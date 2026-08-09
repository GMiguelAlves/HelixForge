#!/usr/bin/env python3

import csv
import math
import sys
from pathlib import Path


def read(path):
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


legacy, native = map(Path, sys.argv[1:3])
for name in ("DEGs_all_results.tsv", "DEGs_significant.tsv", "deg_summary.tsv"):
    left, right = read(legacy / name), read(native / name)
    if len(left) != len(right):
        raise SystemExit(f"{name}: row count differs")
    for lrow, rrow in zip(left, right):
        if lrow.keys() != rrow.keys():
            raise SystemExit(f"{name}: columns differ")
        for key in lrow:
            if key in {"baseMean", "log2FoldChange", "lfcSE", "stat", "pvalue", "padj"} and lrow[key] and rrow[key]:
                if not math.isclose(float(lrow[key]), float(rrow[key]), rel_tol=1e-8, abs_tol=1e-10):
                    raise SystemExit(f"{name}: {key} differs")
            elif lrow[key] != rrow[key]:
                raise SystemExit(f"{name}: {key} differs")
print("Legacy and native DE results are semantically equivalent")
