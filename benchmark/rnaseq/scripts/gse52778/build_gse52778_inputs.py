#!/usr/bin/env python3
"""Create exact HelixForge RC inputs for the full GSE52778 benchmark."""

from __future__ import annotations

import argparse
import csv
import json
import os
import shlex
from pathlib import Path


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def quoted(value: Path | str) -> str:
    return shlex.quote(str(value))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--download-manifest", required=True, type=Path)
    parser.add_argument("--reference-manifest", required=True, type=Path)
    parser.add_argument("--rc-root", required=True, type=Path)
    parser.add_argument("--case-root", required=True, type=Path)
    parser.add_argument("--conda-base", required=True, type=Path)
    parser.add_argument("--de-spec", required=True, type=Path)
    parser.add_argument("--report-genes", required=True, type=Path)
    parser.add_argument("--rna-env", default="rna-tools")
    parser.add_argument("--python-env", default="python-list")
    parser.add_argument("--r-env", default="r-analysis")
    args = parser.parse_args()
    if not os.environ.get("SLURM_JOB_ID"):
        raise SystemExit("input preparation must execute inside a Slurm job")
    if args.case_root.exists():
        raise FileExistsError(f"case root already exists: {args.case_root}")

    registry = read_tsv(args.registry)
    downloads = read_tsv(args.download_manifest)
    reference = json.loads(args.reference_manifest.read_text(encoding="utf-8"))
    if len(registry) != 8 or len(downloads) != 8:
        raise ValueError("the frozen biological benchmark requires exactly eight libraries")
    if reference.get("status") != "REFERENCE_READY":
        raise ValueError("reference manifest is not REFERENCE_READY")
    reference_paths = {entry["role"]: Path(entry["path"]) for entry in reference["artifacts"]}
    for role in ("annotation", "transcriptome", "genome", "tx2gene"):
        path = reference_paths.get(role)
        if path is None or not path.is_file():
            raise ValueError(f"missing reference artifact: {role}")

    download_by_run = {row["run_accession"]: row for row in downloads}
    if len(download_by_run) != 8:
        raise ValueError("download manifest contains duplicate runs")
    expected_conditions = {"untreated": 4, "dexamethasone": 4}
    condition_counts = {condition: 0 for condition in expected_conditions}
    donor_conditions: dict[str, set[str]] = {}
    metadata_rows = []
    for source in sorted(registry, key=lambda row: int(row["sample_index"])):
        run = source["run_accession"]
        downloaded = download_by_run.get(run)
        if downloaded is None:
            raise ValueError(f"download manifest lacks frozen run: {run}")
        for key in ("sample_id", "donor", "condition"):
            if downloaded[key] != source[key]:
                raise ValueError(f"registry/download mismatch for {run}: {key}")
        r1, r2 = Path(downloaded["r1"]), Path(downloaded["r2"])
        for path, size_key in ((r1, "r1_bytes"), (r2, "r2_bytes")):
            if not path.is_file() or path.stat().st_size != int(downloaded[size_key]):
                raise ValueError(f"missing or size-invalid FASTQ: {path}")
        condition = source["condition"]
        if condition not in condition_counts:
            raise ValueError(f"unexpected condition: {condition}")
        condition_counts[condition] += 1
        donor_conditions.setdefault(source["donor"], set()).add(condition)
        metadata_rows.append({
            "dataset": "gse52778_airway",
            "sample_id": source["sample_id"],
            "file_prefix": source["sample_id"],
            "run_accession": run,
            "condition": condition,
            "replicate": source["sample_index"],
            "batch": source["donor"],
            "stage": "primary_airway_smooth_muscle",
            "tissue": "airway_smooth_muscle",
            "sex": "unknown",
            "fastq_1": str(r1),
            "fastq_2": str(r2),
        })
    if condition_counts != expected_conditions:
        raise ValueError(f"invalid condition balance: {condition_counts}")
    if len(donor_conditions) != 4 or any(values != set(expected_conditions) for values in donor_conditions.values()):
        raise ValueError("each of four donors must contain untreated and dexamethasone")

    args.case_root.mkdir(parents=True)
    metadata = args.case_root / "metadata.csv"
    fields = list(metadata_rows[0])
    with metadata.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(metadata_rows)

    pipeline_root = args.case_root / "pipeline"
    settings = args.case_root / "user_settings.sh"
    settings.write_text("\n".join([
        "#!/usr/bin/env bash",
        "export PIPELINE_NAME='helixforge_rnaseq_gse52778_full_benchmark'",
        "export ORGANISM_NAME='Homo_sapiens_GENCODE_49_GRCh38.p14'",
        "export PIPELINE_PROJECTS='gse52778_airway'",
        f"export SCRATCH_ROOT={quoted(args.case_root / 'scratch')}",
        f"export CONDA_BASE={quoted(args.conda_base.resolve())}",
        f"export REF_GENOME_FA={quoted(reference_paths['genome'].resolve())}",
        f"export REF_TRANSCRIPTS_FA={quoted(reference_paths['transcriptome'].resolve())}",
        f"export REF_GTF={quoted(reference_paths['annotation'].resolve())}",
        "export REF_GFF3=''",
        f"export METADATA_FINAL={quoted(metadata.resolve())}",
        f"export METADATA_FINAL_NEW={quoted(metadata.resolve())}",
        f"export SCRIPTS_DIR={quoted((args.rc_root / 'pipelines/rnaseq').resolve())}",
        f"export SALMON_INDEX_DIR={quoted(pipeline_root / '010-reference/salmon_index')}",
        f"export QUANT_DIR={quoted(pipeline_root / '040-alignment/quants')}",
        "export QUANT_METHOD='salmon'",
        "export PIPELINE_EXECUTOR='local'",
        "export THREADS=4",
        "export TRIM_QUALITY=20",
        "export TRIM_LENGTH=20",
        "export SALMON_KMER_SIZE=31",
        "export RUN_SALMON_INDEX=1",
        "export RUN_STAR_INDEX=0",
        "export RUN_STAR_GTF_INDEX=0",
        "export RUN_BATCH_CORRECTION=0",
        "export RUN_GENE_REPORT=1",
        "export BATCH_COLUMN='batch'",
        "export DEG_DESIGN_COVARIATES='batch'",
        f"export RNA_TOOLS_ENV={quoted(args.rna_env)}",
        f"export PYTHON_ENV={quoted(args.python_env)}",
        f"export R_ANALYSIS_ENV={quoted(args.r_env)}",
        "",
    ]), encoding="utf-8")

    pipeline_config = args.case_root / "pipeline_config.sh"
    pipeline_config.write_text("\n".join([
        "#!/usr/bin/env bash",
        f"export PROJECT_DIR={quoted(pipeline_root)}",
        f"export USER_SETTINGS_FILE={quoted(settings.resolve())}",
        f"source {quoted((args.rc_root / 'pipelines/rnaseq/config/pipeline_config.sh').resolve())}",
        "",
    ]), encoding="utf-8")

    de_spec = json.loads(args.de_spec.read_text(encoding="utf-8"))
    if de_spec["design"]["formula"] != "~ batch + condition":
        raise ValueError("frozen DE design must account for donor as batch")
    contrast = de_spec["contrasts"]
    if len(contrast) != 1 or contrast[0]["numerator"] != "dexamethasone" or contrast[0]["denominator"] != "untreated":
        raise ValueError("frozen contrast must be dexamethasone versus untreated")
    de_spec["target_dir"] = str(pipeline_root / "060-deg-analysis/benchmark_airway_primary")
    (args.case_root / "analysis_spec.json").write_text(
        json.dumps(de_spec, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (args.case_root / "report_genes.txt").write_text(
        args.report_genes.read_text(encoding="utf-8"), encoding="utf-8"
    )
    resolved = {
        "workflow": "rnaseq",
        "rnaseq_run_mode": "full",
        "rnaseq_analysis_mode": "quantification",
        "rnaseq_native_alignment": False,
        "rnaseq_import_policy": "production_v1",
        "rnaseq_library_protocol": "full_length",
        "rnaseq_counts_from_abundance": "lengthScaledTPM",
        "rnaseq_report_enabled": True,
        "rnaseq_report_genes": str(args.case_root / "report_genes.txt"),
        "salmon_validate_mappings": True,
        "trim_quality": 20,
        "trim_length": 20,
        "salmon_kmer_size": 31,
        "design": "~ batch + condition",
        "contrast": "condition__dexamethasone_vs_untreated",
        "reference_manifest": str(args.reference_manifest),
        "download_manifest": str(args.download_manifest),
    }
    (args.case_root / "resolved_parameters.json").write_text(
        json.dumps(resolved, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": "complete", "samples": 8, "donors": 4, "design": "~ batch + condition"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
