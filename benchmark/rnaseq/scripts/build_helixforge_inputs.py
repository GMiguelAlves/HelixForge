#!/usr/bin/env python3
"""Create explicit HelixForge RC inputs from a frozen Polyester dataset."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def quoted(value: Path | str) -> str:
    text = str(value)
    if "'" in text or "\n" in text:
        raise ValueError(f"unsupported shell path/value: {text!r}")
    return f"'{text}'"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--design", required=True, type=Path)
    parser.add_argument("--reference-dir", required=True, type=Path)
    parser.add_argument("--fastq-dir", required=True, type=Path)
    parser.add_argument("--rc-root", required=True, type=Path)
    parser.add_argument("--case-root", required=True, type=Path)
    parser.add_argument("--conda-base", required=True, type=Path)
    parser.add_argument("--rna-env", default="rna-tools")
    parser.add_argument("--python-env", default="python-list")
    parser.add_argument("--r-env", default="r-analysis")
    args = parser.parse_args()
    if args.case_root.exists():
        raise FileExistsError(f"case root already exists: {args.case_root}")
    args.case_root.mkdir(parents=True)
    design = json.loads(args.design.read_text(encoding="utf-8"))
    dataset = "POLYESTER_V1"

    metadata = args.case_root / "metadata.csv"
    fields = ["dataset", "sample_id", "file_prefix", "run_accession", "condition", "replicate",
              "batch", "stage", "tissue", "sex", "fastq_1", "fastq_2"]
    with metadata.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for sample in design["experiment"]["samples"]:
            sample_id = sample["sample_id"]
            writer.writerow({
                "dataset": dataset, "sample_id": sample_id, "file_prefix": sample_id,
                "run_accession": f"RUN_{sample_id}", "condition": sample["condition"],
                "replicate": sample["replicate"], "batch": "", "stage": "synthetic",
                "tissue": "synthetic", "sex": "unknown",
                "fastq_1": str((args.fastq_dir / f"{sample_id}_R1.fastq.gz").resolve()),
                "fastq_2": str((args.fastq_dir / f"{sample_id}_R2.fastq.gz").resolve()),
            })

    pipeline_root = args.case_root / "pipeline"
    settings = args.case_root / "user_settings.sh"
    settings.write_text("\n".join([
        "#!/usr/bin/env bash",
        "export PIPELINE_NAME='helixforge_rnaseq_polyester_benchmark'",
        "export ORGANISM_NAME='polyester_ground_truth_v1'",
        f"export PIPELINE_PROJECTS={quoted(dataset)}",
        f"export SCRATCH_ROOT={quoted(args.case_root / 'scratch')}",
        f"export CONDA_BASE={quoted(args.conda_base.resolve())}",
        f"export REF_GENOME_FA={quoted((args.reference_dir / 'synthetic_genome.fa').resolve())}",
        f"export REF_TRANSCRIPTS_FA={quoted((args.reference_dir / 'transcriptome.fa').resolve())}",
        f"export REF_GTF={quoted((args.reference_dir / 'annotation.gtf').resolve())}",
        "export REF_GFF3=''",
        f"export METADATA_FINAL={quoted(metadata.resolve())}",
        f"export METADATA_FINAL_NEW={quoted(metadata.resolve())}",
        f"export SCRIPTS_DIR={quoted((args.rc_root / 'pipelines/rnaseq').resolve())}",
        f"export SALMON_INDEX_DIR={quoted(pipeline_root / '010-reference/salmon_index')}",
        f"export QUANT_DIR={quoted(pipeline_root / '040-alignment/quants')}",
        "export QUANT_METHOD='salmon'",
        "export PIPELINE_EXECUTOR='local'",
        "export THREADS=2",
        "export TRIM_QUALITY=20",
        "export TRIM_LENGTH=20",
        "export SALMON_KMER_SIZE=31",
        "export RUN_SALMON_INDEX=1",
        "export RUN_STAR_INDEX=0",
        "export RUN_STAR_GTF_INDEX=0",
        "export RUN_BATCH_CORRECTION=0",
        "export RUN_GENE_REPORT=0",
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

    de_spec = json.loads((args.rc_root.parent / "benchmark/rnaseq/configs/synthetic_de_spec.json").read_text(
        encoding="utf-8"
    )) if (args.rc_root.parent / "benchmark/rnaseq/configs/synthetic_de_spec.json").is_file() else json.loads(
        (Path(__file__).resolve().parents[1] / "configs/synthetic_de_spec.json").read_text(encoding="utf-8")
    )
    de_spec["target_dir"] = str(pipeline_root / "060-deg-analysis/benchmark_synthetic_primary")
    (args.case_root / "analysis_spec.json").write_text(
        json.dumps(de_spec, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    resolved = {
        "workflow": "rnaseq", "rnaseq_run_mode": "full",
        "rnaseq_analysis_mode": "quantification", "rnaseq_native_alignment": False,
        "rnaseq_import_policy": "production_v1", "rnaseq_library_protocol": "full_length",
        "rnaseq_counts_from_abundance": "lengthScaledTPM", "rnaseq_report_enabled": False,
        "salmon_validate_mappings": True, "trim_quality": 20, "trim_length": 20,
        "salmon_kmer_size": 31, "de_spec": str(args.case_root / "analysis_spec.json"),
    }
    (args.case_root / "resolved_parameters.json").write_text(
        json.dumps(resolved, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": "complete", "samples": len(design["experiment"]["samples"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
