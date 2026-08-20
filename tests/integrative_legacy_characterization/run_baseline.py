#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

try:
    from .baseline_support import BASE_DIR, COMMANDS, FIXTURE_DIR
except ImportError:  # Direct script execution.
    from baseline_support import BASE_DIR, COMMANDS, FIXTURE_DIR


REPO_ROOT = BASE_DIR.parents[1]
LEGACY_ROOT = REPO_ROOT / "pipelines" / "integrative" / "legacy"
CORE = LEGACY_ROOT / "scripts" / "integrative_core.py"


def fixture_environment(output_root: Path) -> dict[str, str]:
    inputs = FIXTURE_DIR / "inputs"
    env = os.environ.copy()
    env.update(
        {
            "PROJECT_DIR": str(LEGACY_ROOT),
            "INTEGRATION_OUTPUT_DIR": str(output_root),
            "RNA_COUNTS_MATRIX": str(inputs / "counts_matrix.tsv"),
            "RNA_NORMALIZED_MATRIX": str(inputs / "tpm_matrix.tsv"),
            "RNA_DEG_RESULTS": str(inputs / "deg_results.tsv"),
            "RNA_METADATA_FILE": str(inputs / "rna_metadata.tsv"),
            "RNA_GENE_CATALOG": str(inputs / "gene_catalog.tsv"),
            "RNA_GENE_CATALOG_EXTRA": "",
            "RNA_EXPRESSION_CONTEXT": "",
            "RNA_WGCNA_HITS": str(inputs / "wgcna_hits.tsv"),
            "RNA_MFUZZ_HITS": str(inputs / "mfuzz_hits.tsv"),
            "RNA_DTU_HITS": str(inputs / "dtu_hits.tsv"),
            "RNA_SPLICING_HITS": str(inputs / "splicing_hits.tsv"),
            "CHIP_METADATA_FILE": str(inputs / "chip_metadata.tsv"),
            "CHIP_ANNOTATED_PEAKS_GLOB": str(inputs / "annotated_peaks*.tsv"),
            "CHIP_PEAK_BED_GLOB": str(inputs / "unused" / "*.bed"),
            "CHIP_PEAK_COUNT_GLOB": str(inputs / "unused" / "*.counts.tsv"),
            "CHIP_DIFF_BINDING_FILE": str(inputs / "differential_binding.tsv"),
            "GENOME_FASTA": str(inputs / "genome.fa"),
            "ANNOTATION_FILE": str(inputs / "annotation.gtf"),
            "FUNCTIONAL_ANNOTATION": str(inputs / "functional_annotation.tsv"),
            "GENES_OF_INTEREST_FILE": str(inputs / "genes_of_interest.txt"),
            "GENE_ID_COLUMN": "gene_id",
            "GENE_NAME_COLUMN": "gene_name",
            "SAMPLE_ID_COLUMN": "sample_id",
            "GROUP_COLUMNS": "stage,condition",
            "RNA_STAGE_COLUMNS": "stage,condition",
            "CONTRAST_ID_COLUMN": "contrast_id",
            "MARK_COLUMN": "mark_or_factor",
            "CONDITION_COLUMN": "condition",
            "PEAK_GENE_WINDOW_BP": "5000",
            "PROMOTER_UPSTREAM_BP": "2000",
            "PROMOTER_DOWNSTREAM_BP": "500",
            "DEG_PADJ_THRESHOLD": "0.05",
            "DEG_LOG2FC_THRESHOLD": "1",
            "DIFF_BINDING_PADJ_THRESHOLD": "0.05",
            "DIFF_BINDING_LOG2FC_THRESHOLD": "1",
            "TOP_CANDIDATES_N": "4",
            "GENE_PANEL_TOP_N": "0",
            "PYTHON_BIN": sys.executable,
        }
    )
    return env


def run(output_root: Path, clean: bool = True) -> None:
    output_root = output_root.resolve()
    if clean and output_root.exists():
        allowed_root = BASE_DIR.resolve()
        try:
            output_root.relative_to(allowed_root)
        except ValueError as error:
            raise SystemExit(f"Refusing to remove output outside {allowed_root}: {output_root}") from error
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    env = fixture_environment(output_root)
    for command in COMMANDS:
        print(f"[characterize] {command}")
        subprocess.run([sys.executable, str(CORE), command], env=env, check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=BASE_DIR / "actual")
    parser.add_argument("--no-clean", action="store_true")
    args = parser.parse_args()
    run(args.output, clean=not args.no_clean)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
