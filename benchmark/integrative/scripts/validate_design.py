#!/usr/bin/env python3
"""Administrative checks for the frozen integrative benchmark design."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def matches_frozen_checksum(path: Path, expected: str) -> bool:
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() == expected:
        return True
    if path.suffix != ".json":
        return False
    # The frozen JSON manifest was first checksummed from a Windows checkout.
    # Accept the same text with Git's Linux line endings, without normalizing
    # scientific tables or allowing any semantic JSON change.
    lf = raw.replace(b"\r\n", b"\n")
    crlf = lf.replace(b"\n", b"\r\n")
    return expected in {
        hashlib.sha256(lf).hexdigest(),
        hashlib.sha256(crlf).hexdigest(),
    }


def main() -> None:
    for path in ROOT.rglob("*.json"):
        json.loads(path.read_text(encoding="utf-8"))
    for path in ROOT.rglob("*.tsv"):
        with path.open(encoding="utf-8", newline="") as handle:
            table = list(csv.DictReader(handle, delimiter="\t"))
        assert table, f"empty TSV: {path}"
        assert all(None not in row for row in table), f"ragged TSV: {path}"
    design = json.loads((ROOT / "configs/synthetic_design.json").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "datasets/synthetic_truth_manifest.json").read_text(encoding="utf-8"))
    with (ROOT / "datasets/synthetic_truth.tsv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    assert len(rows) == design["entity_count"] == manifest["entity_count"] == 1000
    expected = {item["truth_class"]: item["count"] for item in design["classes"]}
    assert Counter(row["truth_class"] for row in rows) == expected
    assert {"MEASURED", "NOT_MEASURED"} <= {row["rna_evidence_state"] for row in rows}
    assert {"MEASURED", "NO_PEAK"} <= {row["chip_evidence_state"] for row in rows}
    assert {"MEASURED", "MISSING", "NOT_APPLICABLE"} <= {row["rna_observation_state"] for row in rows}
    assert {"MEASURED", "MISSING", "NOT_APPLICABLE"} <= {row["chip_observation_state"] for row in rows}
    assert {"MEASURED", "MISSING", "NO_PEAK", "NOT_MEASURED", "NOT_APPLICABLE"} <= (
        {row["rna_evidence_state"] for row in rows}
        | {row["rna_observation_state"] for row in rows}
        | {row["chip_evidence_state"] for row in rows}
        | {row["chip_observation_state"] for row in rows}
        | {row["source_mark"] for row in rows}
    )
    truth = ROOT / "datasets/synthetic_truth.tsv"
    assert manifest["truth_table"]["sha256"] == sha256(truth)
    assert manifest["status"] == "frozen"
    for line in (ROOT / "datasets/SHA256SUMS").read_text(encoding="utf-8").splitlines():
        expected_checksum, relative = line.split("  ", 1)
        path = (ROOT / "datasets" / relative).resolve()
        assert matches_frozen_checksum(path, expected_checksum), f"checksum mismatch: {relative}"
    report = (ROOT / "protocol/design_freeze_report.md").read_text(encoding="utf-8")
    for status in (
        "INTEGRATIVE_BENCHMARK_DESIGN = FROZEN",
        "SYNTHETIC_TRUTH_DESIGN = FROZEN",
        "SCIENTIFIC_EXECUTION = NOT_STARTED",
    ):
        assert status in report
    for markdown in [*ROOT.rglob("*.md"), ROOT.parent / "README.md"]:
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", markdown.read_text(encoding="utf-8")):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            local = target.split("#", 1)[0]
            assert (markdown.parent / local).resolve().exists(), f"broken local link in {markdown}: {target}"
    print("integrative benchmark design: valid")


if __name__ == "__main__":
    main()
