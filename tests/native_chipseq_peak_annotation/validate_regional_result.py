#!/usr/bin/env python3
"""Check the published candidate-to-annotation-to-report fixture, not task exits."""
import argparse
import csv
import hashlib
import json
from pathlib import Path


def read_rows(path):
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def validate(root):
    catalog = root / "chipseq/consensus/fixture.catalog/fixture.catalog.regional_catalog.consensus_result"
    aggregate = root / "chipseq/peak_annotation/peak_annotation_aggregate"
    report = root / "chipseq/report/report_result"
    bed = [line.split("\t") for line in (catalog / "consolidated_peaks.bed").read_text().splitlines()]
    if [(int(r[1]), int(r[2])) for r in bed] != [(100, 500), (501, 601)]:
        raise ValueError("catalog coordinates changed or a positive gap was filled")
    core_path = catalog / "core_supported.bed"
    core = [line.split("\t") for line in core_path.read_text().splitlines()]
    if [(int(r[1]), int(r[2])) for r in core] != [(299, 300)]:
        raise ValueError("one-base support core not preserved separately")
    annotated = read_rows(aggregate / "annotated_peaks.tsv")
    if [(int(r["start"]), int(r["end"])) for r in annotated] != [(100, 500), (501, 601)]:
        raise ValueError("annotation did not preserve complete candidate envelopes")
    associations = read_rows(aggregate / "peak_gene_associations.tsv")
    if {r["gene_id"] for r in associations} != {"left_tail", "right_tail", "single_library"}:
        raise ValueError("tail associations missing or gap gene incorrectly included")
    if not all(r["source_representation"] == "regional_candidate_catalog" and r["occupancy_status"] == "not_assessed" for r in associations):
        raise ValueError("candidate association semantics lost")
    data = json.loads((report / "report.json").read_text())
    representations = data["sections"]["annotation"]["data"]["source_representations"]
    if len(representations) != 1 or representations[0]["source_statistics"]["core_bp"] != 1:
        raise ValueError("report lost candidate/core distinction")
    if representations[0]["support_core"]["sha256"] != hashlib.sha256(core_path.read_bytes()).hexdigest():
        raise ValueError("report core checksum differs from preserved artifact")
    page = (report / "chipseq_report.html").read_text()
    for expected in ("Regional candidate associations", "core_supported.bed", "without filling positive gaps", "not_assessed"):
        if expected not in page:
            raise ValueError(f"HTML is missing {expected}")
    return {"status": "PASS", "candidate_regions": 2, "candidate_bp": 500, "core_bp": 1, "associated_genes": 3, "gap_gene_associated": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", required=True, type=Path)
    print(json.dumps(validate(parser.parse_args().results), indent=2))
