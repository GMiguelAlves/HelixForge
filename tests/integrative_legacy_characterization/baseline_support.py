from __future__ import annotations

import hashlib
import re
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
FIXTURE_DIR = BASE_DIR / "fixture"
GOLDEN_DIR = BASE_DIR / "golden"

COMMANDS = [
    "validate",
    "prepare",
    "harmonize",
    "map-peaks",
    "summarize-rna",
    "summarize-chip",
    "integrate",
    "score",
    "functional",
    "report",
]

OUTPUT_GROUPS = {
    "core": [
        "020-prepared-inputs/input_manifest.tsv",
        "020-prepared-inputs/rnaseq_deg_normalized.tsv",
        "020-prepared-inputs/metadata_combined.tsv",
        "030-id-harmonization/gene_master_table.tsv",
        "030-id-harmonization/unmapped_genes.tsv",
        "030-id-harmonization/epigenetic_machinery_catalog.tsv",
        "040-peak-gene-mapping/peak_to_gene.tsv",
        "040-peak-gene-mapping/promoter_peak_gene_links.tsv",
        "040-peak-gene-mapping/distal_peak_gene_links.tsv",
        "040-peak-gene-mapping/gene_to_peak_summary.tsv",
        "050-rnaseq-summary/rna_gene_summary.tsv",
        "050-rnaseq-summary/rna_expression_by_context.tsv",
        "050-rnaseq-summary/rna_sample_group_mapping.tsv",
        "050-rnaseq-summary/rna_deg_long.tsv",
        "060-chipseq-summary/chip_gene_summary.tsv",
        "060-chipseq-summary/chip_differential_long.tsv",
        "060-chipseq-summary/chip_mark_stage_metadata.tsv",
        "070-integrated-tables/integrated_gene_table.tsv",
        "070-integrated-tables/integrated_by_contrast.tsv",
        "070-integrated-tables/integrative_class_counts.tsv",
        "070-integrated-tables/gene_mark_stage_links.tsv",
        "070-integrated-tables/gene_mark_stage_summary.tsv",
        "070-integrated-tables/mark_to_gene_catalog.tsv",
    ],
    "statistics": [
        "080-candidate-scoring/mark_enrichment_tests.tsv",
        "080-candidate-scoring/gene_mark_stage_signal_matrix.tsv",
        "080-candidate-scoring/gene_mark_stage_correlations.tsv",
    ],
    "scoring": [
        "080-candidate-scoring/candidate_gene_scores.tsv",
        "080-candidate-scoring/top_candidates.tsv",
        "080-candidate-scoring/ranked_candidates_by_contrast.tsv",
        "080-candidate-scoring/ranked_candidates_by_mark.tsv",
        "080-candidate-scoring/ranked_gene_mark_stage_evidence.tsv",
        "080-candidate-scoring/stage_mark_comparison.tsv",
        "080-candidate-scoring/candidate_regulators.tsv",
    ],
    "functional": [
        "100-functional-analysis/functional_enrichment.tsv",
    ],
    "reporting": [
        "010-input-validation/validation_report.tsv",
        "010-input-validation/validation_report.md",
        "110-reports/integrative_report.md",
        "110-reports/integrative_report.html",
    ],
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_text(path: Path, output_root: Path) -> str:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    replacements = []
    for root, token in [(FIXTURE_DIR.resolve(), "<FIXTURE_ROOT>"), (output_root.resolve(), "<OUTPUT_ROOT>")]:
        replacements.extend([(str(root), token), (root.as_posix(), token)])
        if root.drive:
            drive = root.drive.rstrip(":").lower()
            tail = root.as_posix().split(":", 1)[1].lstrip("/")
            replacements.append((f"/mnt/{drive}/{tail}", token))
    for raw, replacement in replacements:
        text = text.replace(raw, replacement)
        text = text.replace(raw.replace("\\", "/"), replacement)
    text = text.replace("<FIXTURE_ROOT>\\", "<FIXTURE_ROOT>/")
    text = text.replace("<OUTPUT_ROOT>\\", "<OUTPUT_ROOT>/")
    text = re.sub(
        r"Generated(?::| )\s*\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}",
        "Generated: <TIMESTAMP>",
        text,
    )
    return text


def iter_expected_outputs():
    for group, paths in OUTPUT_GROUPS.items():
        for relative in paths:
            yield group, relative
