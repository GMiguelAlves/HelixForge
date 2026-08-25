#!/usr/bin/env python3
"""Fail-closed structural validation of a completed synthetic RC execution."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
from pathlib import Path


def require(path: Path) -> Path:
    if not path.is_file() or path.stat().st_size == 0:
        raise FileNotFoundError(path)
    return path


def rows(path: Path, delimiter: str = "\t") -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


def one(candidates: list[Path], label: str) -> Path:
    candidates = [path for path in candidates if path.is_file() and path.stat().st_size > 0]
    if len(candidates) != 1:
        raise ValueError(f"expected one {label}, found {len(candidates)}")
    return candidates[0]


def fastq_records(path: Path) -> int:
    """Count records in a gzipped FASTQ and reject truncated records."""
    line_count = 0
    with gzip.open(require(path), "rt", encoding="utf-8") as handle:
        for line_count, _ in enumerate(handle, start=1):
            pass
    if line_count % 4:
        raise ValueError(f"incomplete FASTQ record in {path}")
    return line_count // 4


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    require(args.case_root / "execution_identity.json")
    identity = json.loads((args.case_root / "execution_identity.json").read_text(encoding="utf-8"))
    if identity.get("rc_sha") != "fc38ada8f592bb57a13467965a718ce0df7fb6ce":
        raise ValueError("incorrect RC SHA")
    if identity.get("nextflow") != "25.10.7" or identity.get("java_major") != 21:
        raise ValueError("incorrect Nextflow/Java runtime identity")

    metadata = rows(require(args.case_root / "metadata.csv"), delimiter=",")
    samples = [row["sample_id"] for row in metadata]
    if len(samples) != 6 or len(set(samples)) != 6:
        raise ValueError("expected six unique samples")
    if [row["condition"] for row in metadata] != ["control"] * 3 + ["treatment"] * 3:
        raise ValueError("condition/sample order differs from frozen design")

    pipeline_info = args.case_root / "results/pipeline_info"
    trace_path = require(pipeline_info / "execution_trace.tsv")
    for filename in ("execution_timeline.html", "execution_report.html", "pipeline_dag.html"):
        require(pipeline_info / filename)
    trace = rows(trace_path)
    if not trace:
        raise ValueError("empty Nextflow trace")
    bad = [row for row in trace if row.get("status") not in {"COMPLETED", "CACHED"}]
    if bad:
        raise ValueError(f"non-successful tasks in trace: {bad[:3]}")
    names = [row["name"] for row in trace]
    required_processes = (
        "RNASEQ_CONTEXT", "RNASEQ_METADATA", "REFERENCE_BUNDLE", "FASTQC_RAW",
        "TRIM_GALORE", "FASTQC_TRIMMED", "MERGE_FASTQ", "FASTQC_MERGED", "MULTIQC",
        "SALMON_INDEX", "SALMON_QUANT", "TX2GENE_BUILD", "SALMON_IMPORT", "DE_PREFLIGHT",
        "DESEQ2_MODEL", "DESEQ2_CONTRAST", "DE_AGGREGATE", "RUN_MANIFEST",
    )
    absent = [process for process in required_processes if not any(process in name for name in names)]
    if absent:
        raise ValueError(f"missing expected processes: {absent}")
    forbidden = [name for name in names if "STAR_INDEX" in name or "STAR_ALIGN" in name]
    if forbidden:
        raise ValueError(f"STAR unexpectedly executed: {forbidden}")
    if any("RNASEQ_GENE_REPORT" in name for name in names):
        raise ValueError("truth-sensitive candidate gene report unexpectedly executed")

    require(args.case_root / "scratch/POLYESTER_V1/multiqc_030/POLYESTER_V1_multiqc_030.html")
    pipeline = args.case_root / "pipeline"
    for filename in ("counts_matrix.tsv", "tpm_matrix.tsv", "length_matrix.tsv",
                     "summarized_experiment.rds"):
        require(pipeline / f"050-quantification/{filename}")
    require(args.case_root / "results/pipeline_info/native_import/tximport/import_manifest.json")

    salmon = {}
    for sample in samples:
        quant = pipeline / f"040-alignment/quants/POLYESTER_V1/{sample}"
        for relative in ("quant.sf", "cmd_info.json", "lib_format_counts.json", "aux_info/meta_info.json"):
            require(quant / relative)
        meta = json.loads((quant / "aux_info/meta_info.json").read_text(encoding="utf-8"))
        processed, mapped = int(meta["num_processed"]), int(meta["num_mapped"])
        merged = args.case_root / "scratch/POLYESTER_V1/trimmed_merged"
        read1 = fastq_records(merged / f"{sample}_R1_trimmed.fastq.gz")
        read2 = fastq_records(merged / f"{sample}_R2_trimmed.fastq.gz")
        if read1 != read2:
            raise ValueError(f"{sample}: post-trim FASTQ mates differ ({read1} != {read2})")
        if processed != read1:
            raise ValueError(
                f"{sample}: Salmon processed {processed}, post-trim FASTQ contains {read1} pairs"
            )
        salmon[sample] = {"processed": processed, "mapped": mapped,
                          "mapping_rate": mapped / processed,
                          "raw_pairs": 2_000_000,
                          "retained_pair_rate": processed / 2_000_000}

    tx2gene_rows = rows(require(pipeline / "050-quantification/tx2gene.tsv"))
    tx_to_gene = {row["transcript_id"]: row["gene_id"] for row in tx2gene_rows}
    input_genes = set(tx_to_gene.values())
    if len(input_genes) != 1200 or len(tx_to_gene) != 2400:
        raise ValueError("tx2gene does not contain the frozen 1,200-gene/2,400-transcript universe")
    first_quant = pipeline / f"040-alignment/quants/POLYESTER_V1/{samples[0]}/quant.sf"
    quantified_transcripts = {row["Name"] for row in rows(require(first_quant))}
    if not quantified_transcripts <= tx_to_gene.keys():
        raise ValueError("Salmon quantification contains transcripts absent from tx2gene")
    effective_genes = {tx_to_gene[transcript] for transcript in quantified_transcripts}
    counts_rows = rows(require(pipeline / "050-quantification/counts_matrix.tsv"))
    count_genes = {row["gene_id"] for row in counts_rows}
    if count_genes != effective_genes:
        raise ValueError("Import gene universe differs from Salmon's indexed transcript universe")

    index_info = json.loads(require(
        pipeline_info / "native_quantification/salmon_index/info.json"
    ).read_text(encoding="utf-8"))
    index_log = require(
        pipeline_info
        / "native_quantification/salmon_index/"
        "salmon.transcriptome.index.salmon_index_reports/salmon_index.log"
    ).read_text(encoding="utf-8")
    removed_transcripts = len(tx_to_gene) - len(quantified_transcripts)
    if index_info.get("keep_duplicates") is not False or removed_transcripts != 24:
        raise ValueError("unexpected Salmon duplicate-transcript indexing policy/result")
    if "Removed 24 transcripts that were sequence duplicates" not in index_log:
        raise ValueError("Salmon duplicate removal is not documented in its index log")

    de_table = one(list((pipeline / "060-deg-analysis").rglob("differential_expression_results.tsv")),
                   "aggregate differential expression table")
    de_rows = rows(de_table)
    if {row["gene_id"] for row in de_rows} != effective_genes:
        raise ValueError("DE table does not preserve the complete estimable Import API universe")
    run_manifests = sorted((args.case_root / "results").rglob("rnaseq_run_manifest.json"))
    if not run_manifests:
        raise ValueError("RNA-seq run manifest is absent")
    manifest_payloads = [require(path).read_bytes() for path in run_manifests]
    if any(payload != manifest_payloads[0] for payload in manifest_payloads[1:]):
        raise ValueError("published RNA-seq run manifest copies differ")
    run_manifest = run_manifests[0]
    manifest = json.loads(manifest_payloads[0])
    if manifest.get("status") != "complete":
        raise ValueError("terminal run manifest is not complete")

    report = {
        "schema_version": "1.0", "status": "pass", "samples": samples,
        "tasks": len(trace), "cached_tasks": sum(row["status"] == "CACHED" for row in trace),
        "salmon": salmon, "input_genes": len(input_genes),
        "indexed_transcripts": len(quantified_transcripts),
        "duplicate_transcripts_removed": removed_transcripts,
        "estimable_genes": len(effective_genes), "de_genes": len(de_rows),
        "run_manifests": [str(path.relative_to(args.case_root)) for path in run_manifests],
        "candidate_gene_report": "NOT_APPLICABLE_BY_FROZEN_SYNTHETIC_DESIGN",
        "star": "EXCLUDED_BY_FROZEN_PRODUCTION_PATH",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "pass", "tasks": len(trace), "samples": len(samples)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
