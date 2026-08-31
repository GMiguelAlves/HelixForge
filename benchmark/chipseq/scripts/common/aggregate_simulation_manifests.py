#!/usr/bin/env python3
"""Aggregate three frozen ChIPs library manifests without inspecting results."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", action="append", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    libraries = [json.loads(path.read_text(encoding="utf-8")) for path in args.manifest]
    by_sample = {library["sample"]: library for library in libraries}
    expected = {"chip_rep1", "chip_rep2", "input"}
    if set(by_sample) != expected:
        raise ValueError(f"expected {sorted(expected)}, observed {sorted(by_sample)}")
    commits = {library["chips_commit"] for library in libraries}
    binaries = {library["chips_binary_sha256"] for library in libraries}
    sources = {library["chips_source_sha256"] for library in libraries}
    references = {library["reference_sha256"] for library in libraries}
    if any(len(values) != 1 for values in (commits, binaries, sources, references)):
        raise ValueError("simulation runtime/reference identity differs between libraries")
    document = {
        "schema_version": "1.0",
        "type": "chips_simulation",
        "chips_version": "v2.4",
        "chips_commit": next(iter(commits)),
        "chips_binary_sha256": next(iter(binaries)),
        "chips_source_sha256": next(iter(sources)),
        "reference_sha256": next(iter(references)),
        "seeds": {sample: by_sample[sample]["seed"] for sample in sorted(expected)},
        "libraries": [by_sample[sample] for sample in sorted(expected)],
        "status": "complete",
    }
    args.output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
