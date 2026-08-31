#!/usr/bin/env python3
"""Capture and validate the frozen ENCODE Real Broad metadata."""

from __future__ import annotations

import argparse
import csv
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ENCODE_API = "https://www.encodeproject.org"
USER_AGENT = "HelixForge real-broad benchmark metadata audit"
FILE_ACCESSIONS = (
    "ENCFF000BXP", "ENCFF000BXN", "ENCFF000BWK",
    "ENCFF049HUP", "ENCFF366NNJ", "ENCFF356LFX",
)
EXPERIMENT_ACCESSIONS = ("ENCSR000AKQ", "ENCSR000AKY")


def fetch_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def accession_values(values) -> set[str]:
    result = set()
    for value in values or []:
        path = value.get("@id", "") if isinstance(value, dict) else str(value)
        parts = path.strip("/").split("/")
        if parts:
            result.add(parts[-1])
    return result


def audit_rows(record: dict) -> list[dict]:
    rows = []
    for level, entries in sorted(record.get("audit", {}).items()):
        for entry in entries:
            rows.append({
                "level": level,
                "category": entry.get("category"),
                "detail": entry.get("detail"),
                "path": entry.get("path"),
            })
    return rows


def embedded(value, field: str):
    return value.get(field) if isinstance(value, dict) else None


def joined(value) -> str:
    return ",".join(str(item) for item in value or [])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", required=True, type=Path)
    parser.add_argument("--references", required=True, type=Path)
    parser.add_argument("--execution-config", required=True, type=Path)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-tsv", required=True, type=Path)
    args = parser.parse_args()

    with args.samples.open(encoding="utf-8", newline="") as handle:
        samples = {row["file_accession"]: row for row in csv.DictReader(handle, delimiter="\t")}
    with args.references.open(encoding="utf-8", newline="") as handle:
        references = {
            row["accession_or_release"]: row for row in csv.DictReader(handle, delimiter="\t")
            if row["accession_or_release"] in {"ENCFF049HUP", "ENCFF366NNJ", "ENCFF356LFX"}
        }
    execution = json.loads(args.execution_config.read_text(encoding="utf-8"))
    experiments = {
        accession: fetch_json(f"{ENCODE_API}/experiments/{accession}/?format=json")
        for accession in EXPERIMENT_ACCESSIONS
    }
    files = {
        accession: fetch_json(f"{ENCODE_API}/files/{accession}/?format=json")
        for accession in FILE_ACCESSIONS
    }

    expected_accessions = set(samples) | set(references)
    if expected_accessions != set(FILE_ACCESSIONS):
        raise ValueError(f"frozen accession mismatch: {sorted(expected_accessions)}")

    ip_experiment = experiments[execution["dataset"]["experiment"]]
    checks = {
        "experiments_released": all(item.get("status") == "released" for item in experiments.values()),
        "files_released": all(item.get("status") == "released" for item in files.values()),
        "h3k27me3_target": embedded(ip_experiment.get("target"), "label") == "H3K27me3",
        "k562": all("K562" in item.get("biosample_summary", "") for item in experiments.values()),
        "control_experiment": execution["dataset"]["control_experiment"] in accession_values(ip_experiment.get("possible_controls")),
        "control_file": execution["dataset"]["control_file"] == "ENCFF000BWK",
    }

    for accession, expected in samples.items():
        observed = files[accession]
        checks[f"{accession}_dataset"] = observed.get("dataset") == f"/experiments/{expected['experiment_accession']}/"
        checks[f"{accession}_md5"] = observed.get("md5sum") == expected["md5"]
        checks[f"{accession}_size"] = observed.get("file_size") == int(expected["file_size_bytes"])
        checks[f"{accession}_reads"] = observed.get("read_count") == int(expected["read_count"])
        checks[f"{accession}_length"] = observed.get("read_length") == int(expected["read_length_bp"])
        checks[f"{accession}_layout"] = observed.get("run_type") == "single-ended"
        checks[f"{accession}_replicate"] = int(expected["replicate"]) in observed.get("biological_replicates", [])

    for accession, expected in references.items():
        observed = files[accession]
        checks[f"{accession}_assembly"] = observed.get("assembly") == expected["assembly"]
        if expected["md5"] != "NA":
            checks[f"{accession}_md5"] = observed.get("md5sum") == expected["md5"]

    if not all(checks.values()):
        failed = sorted(name for name, passed in checks.items() if not passed)
        raise ValueError(f"DATASET_AVAILABILITY_CONFLICT: {failed}")

    compact_experiments = [{
        "accession": accession,
        "status": item.get("status"),
        "assay_title": item.get("assay_title"),
        "target": embedded(item.get("target"), "label"),
        "biosample_summary": item.get("biosample_summary"),
        "possible_controls": sorted(accession_values(item.get("possible_controls"))),
        "date_released": item.get("date_released"),
        "audit": audit_rows(item),
    } for accession, item in experiments.items()]

    compact_files = []
    table_rows = []
    for accession, item in files.items():
        experiment_accession = item.get("dataset", "").strip("/").split("/")[-1]
        experiment = experiments.get(experiment_accession, {})
        warnings = audit_rows(item)
        compact_files.append({
            "accession": accession,
            "status": item.get("status"),
            "experiment_accession": experiment_accession,
            "file_format": item.get("file_format"),
            "output_type": item.get("output_type"),
            "assembly": item.get("assembly"),
            "file_size": item.get("file_size"),
            "md5sum": item.get("md5sum"),
            "content_md5sum": item.get("content_md5sum"),
            "read_length": item.get("read_length"),
            "read_count": item.get("read_count"),
            "run_type": item.get("run_type"),
            "biological_replicates": item.get("biological_replicates", []),
            "technical_replicates": item.get("technical_replicates", []),
            "download_url": f"{ENCODE_API}{item.get('href')}",
            "audit": warnings,
        })
        table_rows.append({
            "experiment_accession": experiment_accession,
            "file_accession": accession,
            "biological_replicates": joined(item.get("biological_replicates")),
            "technical_replicates": joined(item.get("technical_replicates")),
            "target": embedded(experiment.get("target"), "label") or ("INPUT" if experiment_accession == "ENCSR000AKY" else ""),
            "cell_line": experiment.get("biosample_summary"),
            "layout": item.get("run_type"),
            "read_length_bp": item.get("read_length"),
            "assembly": item.get("assembly"),
            "file_format": item.get("file_format"),
            "output_type": item.get("output_type"),
            "file_size_bytes": item.get("file_size"),
            "md5": item.get("md5sum"),
            "status": item.get("status"),
            "quality_warnings": ";".join(sorted({row["category"] for row in warnings if row["category"]})),
        })

    result = {
        "schema_version": "1.0",
        "type": "real_broad_public_metadata_snapshot",
        "status": "METADATA_VALIDATED",
        "captured_utc": datetime.now(timezone.utc).isoformat(),
        "source": ENCODE_API,
        "checks": checks,
        "experiments": compact_experiments,
        "files": compact_files,
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    with args.output_tsv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(table_rows[0]), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(table_rows)


if __name__ == "__main__":
    main()
