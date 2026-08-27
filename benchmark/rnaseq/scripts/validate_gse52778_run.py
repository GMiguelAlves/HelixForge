#!/usr/bin/env python3
"""Fail-closed structural validation of the completed biological RC run."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


def require(path: Path) -> Path:
    if not path.is_file() or path.stat().st_size == 0:
        raise FileNotFoundError(path)
    return path


def rows(path: Path, delimiter: str = "\t") -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


def one(candidates: list[Path], label: str) -> Path:
    selected = [path for path in candidates if path.is_file() and path.stat().st_size > 0]
    if len(selected) != 1:
        raise ValueError(f"expected one {label}, found {len(selected)}")
    return selected[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-root", required=True, type=Path)
    parser.add_argument("--reference-manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    identity = json.loads(require(args.case_root / "execution_identity.json").read_text(encoding="utf-8"))
    if identity.get("status") != "complete":
        raise ValueError("execution identity is not complete")
    if identity.get("rc_sha") != "fc38ada8f592bb57a13467965a718ce0df7fb6ce":
        raise ValueError("incorrect RC SHA")
    if identity.get("nextflow") != "25.10.7" or identity.get("java_major") != 21:
        raise ValueError("incorrect Nextflow/Java runtime identity")
    if identity.get("design") != "~ batch + condition" or identity.get("contrast") != "dexamethasone_vs_untreated":
        raise ValueError("execution identity does not preserve paired design/contrast")

    metadata = rows(require(args.case_root / "metadata.csv"), delimiter=",")
    if len(metadata) != 8 or len({row["sample_id"] for row in metadata}) != 8:
        raise ValueError("expected eight unique samples")
    if Counter(row["condition"] for row in metadata) != Counter({"untreated": 4, "dexamethasone": 4}):
        raise ValueError("condition balance differs from frozen design")
    donors: defaultdict[str, set[str]] = defaultdict(set)
    for row in metadata:
        donors[row["batch"]].add(row["condition"])
    if len(donors) != 4 or any(values != {"untreated", "dexamethasone"} for values in donors.values()):
        raise ValueError("donor pairing differs from frozen design")

    reference = json.loads(require(args.reference_manifest).read_text(encoding="utf-8"))
    if reference.get("status") != "REFERENCE_READY" or reference.get("release") != "GENCODE_49":
        raise ValueError("invalid frozen reference")
    if reference.get("id_policy", {}).get("ignoreTxVersion") is not False or reference.get("id_policy", {}).get("ignoreAfterBar") is not False:
        raise ValueError("reference ID policy differs from production_v1")

    pipeline_info = args.case_root / "results/pipeline_info"
    trace = rows(require(pipeline_info / "execution_trace.tsv"))
    for filename in ("execution_timeline.html", "execution_report.html", "pipeline_dag.html"):
        require(pipeline_info / filename)
    bad = [row for row in trace if row.get("status") not in {"COMPLETED", "CACHED"}]
    if bad:
        raise ValueError(f"non-successful tasks in trace: {bad[:3]}")
    names = [row["name"] for row in trace]
    required_processes = (
        "RNASEQ_CONTEXT", "RNASEQ_METADATA", "REFERENCE_BUNDLE", "FASTQC_RAW",
        "TRIM_GALORE", "FASTQC_TRIMMED", "MERGE_FASTQ", "FASTQC_MERGED", "MULTIQC",
        "SALMON_INDEX", "SALMON_QUANT", "TX2GENE_BUILD", "SALMON_IMPORT", "DE_PREFLIGHT",
        "DESEQ2_MODEL", "DESEQ2_CONTRAST", "DE_AGGREGATE", "RNASEQ_GENE_REPORT", "RUN_MANIFEST",
    )
    absent = [process for process in required_processes if not any(process in name for name in names)]
    if absent:
        raise ValueError(f"missing expected processes: {absent}")
    if any("STAR_INDEX" in name or "STAR_ALIGN" in name for name in names):
        raise ValueError("experimental STAR provider unexpectedly executed")

    pipeline = args.case_root / "pipeline"
    matrices = {}
    for filename in ("counts_matrix.tsv", "tpm_matrix.tsv", "length_matrix.tsv"):
        path = require(pipeline / f"050-quantification/{filename}")
        matrices[filename] = rows(path)
    require(pipeline / "050-quantification/summarized_experiment.rds")
    sample_ids = [row["sample_id"] for row in metadata]
    salmon = {}
    transcript_universe: set[str] | None = None
    for sample in sample_ids:
        quant = pipeline / f"040-alignment/quants/gse52778_airway/{sample}"
        for relative in ("quant.sf", "cmd_info.json", "lib_format_counts.json", "aux_info/meta_info.json"):
            require(quant / relative)
        meta = json.loads((quant / "aux_info/meta_info.json").read_text(encoding="utf-8"))
        processed, mapped = int(meta["num_processed"]), int(meta["num_mapped"])
        if processed <= 0 or mapped < 0 or mapped > processed:
            raise ValueError(f"invalid Salmon counts for {sample}")
        current = {row["Name"] for row in rows(quant / "quant.sf")}
        if transcript_universe is None:
            transcript_universe = current
        elif current != transcript_universe:
            raise ValueError(f"Salmon transcript universe differs for {sample}")
        salmon[sample] = {"processed": processed, "mapped": mapped, "mapping_rate": mapped / processed}

    tx2gene_rows = rows(require(pipeline / "050-quantification/tx2gene.tsv"))
    tx_to_gene = {row["transcript_id"]: row["gene_id"] for row in tx2gene_rows}
    if len(tx_to_gene) != int(reference["transcripts"]):
        raise ValueError("tx2gene transcript count differs from reference manifest")
    assert transcript_universe is not None
    if not transcript_universe <= tx_to_gene.keys():
        raise ValueError("quantified transcripts are absent from tx2gene")
    estimable_genes = {tx_to_gene[transcript] for transcript in transcript_universe}
    for filename, matrix_rows in matrices.items():
        if {row["gene_id"] for row in matrix_rows} != estimable_genes:
            raise ValueError(f"{filename} gene universe differs from quantified transcripts")
        if set(matrix_rows[0]).difference({"gene_id"}) != set(sample_ids):
            raise ValueError(f"{filename} sample columns differ from frozen metadata")

    de_table = one(list((pipeline / "060-deg-analysis").rglob("differential_expression_results.tsv")),
                   "aggregate differential expression table")
    de_rows = rows(de_table)
    if {row["gene_id"] for row in de_rows} != estimable_genes:
        raise ValueError("DE table does not preserve the estimable Import universe")
    report_root = pipeline / "090-search-gene/results"
    report_html = require(report_root / "gene_set_report.html")
    report_manifest = require(report_root / "manifest.json")
    require(report_root / "context.json")
    require(report_root / "sessionInfo.txt")
    require(report_root / "tables/gene_catalog.tsv")
    require(report_root / "tables/expression_long.tsv")
    report_payload = json.loads(report_manifest.read_text(encoding="utf-8"))
    if report_payload.get("status") != "complete":
        raise ValueError("candidate-gene report manifest is not complete")
    if report_payload.get("provider") != "candidate_genes_v1":
        raise ValueError("unexpected candidate-gene report provider")
    if report_payload.get("sample_count") != 8:
        raise ValueError("candidate-gene report does not contain all eight samples")
    report_context = json.loads((report_root / "context.json").read_text(encoding="utf-8"))
    if report_context.get("group_count") != 2 or report_payload.get("query_count") != 9:
        raise ValueError("candidate-gene report does not preserve the frozen two groups and nine queries")
    report_plots = [path for path in (report_root / "plots").glob("*.png") if path.stat().st_size > 100]
    if not report_plots:
        raise ValueError("candidate-gene report produced no non-empty scientific plots")

    run_manifests = sorted((args.case_root / "results").rglob("rnaseq_run_manifest.json"))
    if not run_manifests:
        raise ValueError("terminal RNA-seq run manifest is absent")
    payloads = [require(path).read_bytes() for path in run_manifests]
    if any(payload != payloads[0] for payload in payloads[1:]):
        raise ValueError("terminal manifest copies differ")
    terminal = json.loads(payloads[0])
    if terminal.get("status") != "complete":
        raise ValueError("terminal run manifest is not complete")

    multiqc_findings = []
    multiqc_versions = list((args.case_root / "scratch/gse52778_airway").rglob("multiqc_software_versions.txt"))
    if not multiqc_versions:
        multiqc_findings.append("KNOWN_REPORTING_LIMITATION:MULTIQC_SOFTWARE_TABLE_ABSENT")
    report = {
        "schema_version": "1.0", "status": "pass", "samples": sample_ids,
        "donors": sorted(donors), "conditions": dict(Counter(row["condition"] for row in metadata)),
        "tasks": len(trace), "cached_tasks": sum(row["status"] == "CACHED" for row in trace),
        "salmon": salmon, "reference_transcripts": int(reference["transcripts"]),
        "indexed_transcripts": len(transcript_universe), "estimable_genes": len(estimable_genes),
        "de_genes": len(de_rows), "de_table": str(de_table.relative_to(args.case_root)),
        "gene_report": str(report_html.relative_to(args.case_root)),
        "gene_report_plots": len(report_plots),
        "gene_report_groups": 2, "gene_report_queries": 9,
        "run_manifests": [str(path.relative_to(args.case_root)) for path in run_manifests],
        "multiqc_findings": multiqc_findings,
        "star": "EXCLUDED_BY_FROZEN_PRODUCTION_PATH",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "pass", "tasks": len(trace), "samples": len(sample_ids)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
