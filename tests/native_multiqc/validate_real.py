#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def require(path: Path) -> Path:
    if not path.exists() or (path.is_file() and path.stat().st_size == 0):
        raise AssertionError(f"missing or empty artifact: {path}")
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()

    report = require(args.root / "results/certification_multiqc.html")
    data_dir = require(args.root / "results/certification_multiqc_data")
    fastqc_table = require(data_dir / "multiqc_fastqc.txt")
    general_stats = require(data_dir / "multiqc_general_stats.txt")
    versions = require(
        args.root
        / "out/pipeline_info/native_qc/multiqc/certification.multiqc.versions.yml"
    )
    status = require(
        args.root
        / "out/pipeline_info/native_qc/multiqc/certification.multiqc.multiqc.done"
    )
    trace = require(args.root / "out/execution_trace.tsv")
    image_digest = require(args.root / "image_digest.txt").read_text(
        encoding="utf-8"
    ).strip()
    if "@sha256:" not in image_digest:
        raise AssertionError(f"invalid OCI repository digest: {image_digest!r}")

    html = report.read_text(encoding="utf-8", errors="replace")
    if "MultiQC" not in html:
        raise AssertionError("rendered HTML does not identify MultiQC")

    with fastqc_table.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    if len(rows) != 2:
        raise AssertionError(f"expected two FastQC records, observed {len(rows)}")
    observed = {row["Sample"]: row for row in rows}
    expected = {
        "sample_a_R1": {"Total Sequences": 12.0, "%GC": 45.0},
        "sample_b_R1": {"Total Sequences": 18.0, "%GC": 52.0},
    }
    for sample, metrics in expected.items():
        if sample not in observed:
            raise AssertionError(f"MultiQC FastQC table is missing {sample}")
        for metric, value in metrics.items():
            actual = float(observed[sample][metric])
            if actual != value:
                raise AssertionError(
                    f"unexpected {sample} {metric}: {actual}; expected {value}"
                )

    version_text = versions.read_text(encoding="utf-8")
    if "1.17" not in version_text:
        raise AssertionError(f"unexpected MultiQC version record: {version_text!r}")
    status_doc = json.loads(status.read_text(encoding="utf-8"))
    if status_doc.get("status") != "complete":
        raise AssertionError(f"unexpected process status: {status_doc}")

    summary = {
        "schema_version": "1.0",
        "status": "pass",
        "multiqc_version": "1.17",
        "container_digest": image_digest,
        "fastqc_records": len(rows),
        "validated_metrics": expected,
        "artifacts": {
            "html": str(report),
            "data": str(data_dir),
            "fastqc_table": str(fastqc_table),
            "general_stats": str(general_stats),
            "versions": str(versions),
            "trace": str(trace),
        },
    }
    (args.root / "certification.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
