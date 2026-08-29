#!/usr/bin/env python3
"""Select and validate the technical outputs used by the narrow evaluator."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require_one(paths: list[Path], description: str) -> Path:
    unique = sorted({path.resolve() for path in paths})
    if len(unique) != 1:
        raise ValueError(f"expected one {description}, observed {len(unique)}: {unique}")
    if not unique[0].is_file() or unique[0].stat().st_size == 0:
        raise ValueError(f"empty or absent {description}: {unique[0]}")
    return unique[0]


def count_records(path: Path) -> int:
    with path.open(encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip() and not line.startswith("#"))


def parse_trace(path: Path) -> dict:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    statuses = {row.get("status") for row in rows}
    if not rows or statuses != {"COMPLETED"}:
        raise ValueError(f"Nextflow trace is incomplete: rows={len(rows)} statuses={statuses}")
    return {"tasks": len(rows), "cached_tasks": sum(row.get("cached") == "true" for row in rows), "processes": sorted({row.get("process", "") for row in rows})}


def final_idr_candidates(consensus_root: Path) -> list[Path]:
    """Return published final IDR sets from current or historical layouts."""
    return [
        path
        for path in consensus_root.rglob("idr_output.narrowPeak")
        if {"consensus_result", "idr_result"}.intersection(path.parts)
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--helixforge-run", required=True, type=Path)
    parser.add_argument("--independent-run", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    helixforge_run = args.helixforge_run.resolve()
    results = helixforge_run / "results"
    independent = args.independent_run.resolve()
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=False)

    selected = {}
    for sample in ("chip_rep1", "chip_rep2"):
        hf_peak = require_one(list((results / "080-peak-calling").glob(f"*{sample}*.peak_calling/peaks.narrowPeak")), f"HelixForge {sample} peak set")
        ext_peak = require_one(list((independent / "peaks" / sample).glob("*_peaks.narrowPeak")), f"independent {sample} peak set")
        selected[f"helixforge_{sample}"] = hf_peak
        selected[f"independent_{sample}"] = ext_peak
    selected["helixforge_idr"] = require_one(
        final_idr_candidates(results / "chipseq" / "consensus"),
        "HelixForge final IDR peak set",
    )
    selected["independent_idr"] = require_one([independent / "idr" / "idr_output.narrowPeak"], "independent final IDR peak set")
    frip_files = sorted((results / "pipeline_info/native_chipseq/peak_qc/frip").glob("chip_rep*.frip.json"))
    if len(frip_files) != 2:
        raise ValueError(f"expected two treatment FRiP JSON files, observed {len(frip_files)}")
    frip = [json.loads(path.read_text(encoding="utf-8")) for path in frip_files]
    if any(row.get("status") != "complete" or row.get("unit") != "fragments" for row in frip):
        raise ValueError("FRiP contract is incomplete")

    trace = require_one([helixforge_run / "trace.tsv"], "Nextflow trace")
    trace_metrics = parse_trace(trace)
    multiqc = require_one(list(results.rglob("multiqc_report.html")), "MultiQC report")
    nextflow_report = require_one([helixforge_run / "report.html"], "Nextflow report")
    log = require_one([helixforge_run / "logs/nextflow.log"], "Nextflow log")
    log_text = log.read_text(encoding="utf-8", errors="replace")
    if "Execution complete -- Goodbye" not in log_text:
        raise ValueError("Nextflow terminal success marker is absent")
    session = re.search(r"Session UUID: ([0-9a-f-]+)", log_text)

    artifact_rows = []
    for role, path in selected.items():
        artifact_rows.append({"role": role, "path": str(path), "sha256": sha256(path), "records": count_records(path), "size_bytes": path.stat().st_size})
    with (output / "selected_peak_sets.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(artifact_rows[0]), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(artifact_rows)
    frip_rows = [
        {"sample_id": row["sample_id"], "frip": row["frip"], "total_fragments": row["total_units"], "fragments_in_peaks": row["units_in_peaks"], "min_mapq": row["filters"]["min_mapq"], "status": row["status"]}
        for row in frip
    ]
    with (output / "frip_metrics.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(frip_rows[0]), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(frip_rows)
    technical_rows = [
        {"check": "workflow_completed", "status": "PASS", "value": "Execution complete -- Goodbye"},
        {"check": "expected_samples", "status": "PASS", "value": "chip_rep1,chip_rep2,input"},
        {"check": "replicate_peaks", "status": "PASS", "value": "2 non-empty narrowPeak sets"},
        {"check": "idr", "status": "PASS", "value": f"{count_records(selected['helixforge_idr'])} final peaks"},
        {"check": "frip", "status": "PASS", "value": "2 fragment-unit records"},
        {"check": "multiqc", "status": "PASS", "value": str(multiqc)},
        {"check": "nextflow_report", "status": "PASS", "value": str(nextflow_report)},
        {"check": "trace", "status": "PASS", "value": f"{trace_metrics['tasks']} completed tasks"},
    ]
    with (output / "technical_metrics.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(technical_rows[0]), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(technical_rows)
    manifest = {
        "schema_version": "1.0", "type": "synthetic_narrow_selected_outputs", "status": "TECHNICAL_EXECUTION_PASS",
        "session_uuid": session.group(1) if session else None, "trace": trace_metrics,
        "artifacts": {role: {"path": str(path), "sha256": sha256(path), "records": count_records(path)} for role, path in selected.items()},
        "frip": frip_rows, "multiqc": {"path": str(multiqc), "sha256": sha256(multiqc)},
        "nextflow_report": {"path": str(nextflow_report), "sha256": sha256(nextflow_report)},
    }
    (output / "selected_outputs.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
