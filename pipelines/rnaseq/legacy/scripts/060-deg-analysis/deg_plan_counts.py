#!/usr/bin/env python3

import csv
import sys

with open(sys.argv[1], newline="", encoding="utf-8") as handle:
    rows = list(csv.DictReader(handle))

print(f"analyses={len(rows)}")
