#!/usr/bin/env python3
"""Generate the frozen integration truth without importing HelixForge code."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


FIELDS = [
    "gene_id", "source_rna_gene_id", "source_chip_gene_id", "truth_class",
    "expected_regulatory_pattern", "expected_legacy_evidence_class",
    "rna_evidence_state", "rna_observation_state", "rna_direction",
    "rna_log2fc", "rna_padj", "chip_evidence_state", "chip_observation_state",
    "source_mark", "expected_canonical_mark", "mark_role", "chip_direction",
    "chip_log2fc", "chip_padj", "peak_relationships", "peak_count",
    "expected_peak_scope", "multi_gene_region_id", "context_type",
    "source_context", "expected_canonical_context", "source_rna_contrast_id",
    "source_chip_contrast_id", "expected_canonical_contrast_id",
    "normalization_case", "explicit_missing_observation", "difficulty_tier",
    "candidate_priority", "candidate_context_flags", "truth_note",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fmt(value: float | str) -> str:
    return f"{value:.8g}" if isinstance(value, float) else value


def mark_for(index: int, predicted: str) -> tuple[str, str, str, int]:
    if predicted == "ACTIVATION":
        choices = [
            ("H3K27ac", "H3K27ac", "ACTIVATING", 1),
            ("h3k4me3", "H3K4me3", "ACTIVATING", 1),
            ("H3K27me3", "H3K27me3", "REPRESSIVE", -1),
            ("H3K9me3", "H3K9me3", "REPRESSIVE", -1),
        ]
    else:
        choices = [
            ("h3k27ac", "H3K27ac", "ACTIVATING", -1),
            ("H3K4me3", "H3K4me3", "ACTIVATING", -1),
            ("H3K27me3", "H3K27me3", "REPRESSIVE", 1),
            ("h3k9me3", "H3K9me3", "REPRESSIVE", 1),
        ]
    return choices[index % len(choices)]


def sources(gene: str, index: int) -> tuple[str, str, str]:
    case = index % 40
    if case == 0:
        return f"gene:{gene}", gene, "strip_literal_gene_prefix"
    if case == 1:
        return f"{gene}.1", gene, "strip_version_suffix_opt_in"
    if case == 2:
        return f"RNA_ALIAS_{index:04d}", gene, "explicit_alias_map"
    return gene, gene, "exact"


def peak_design(index: int, has_peak: bool) -> tuple[str, int, str, str]:
    if not has_peak:
        return "NOT_APPLICABLE", 0, "NOT_APPLICABLE", ""
    designs = [
        ("promoter", 1, "promoter"),
        ("promoter;promoter", 2, "promoter"),
        ("proximal", 1, "distal"),
        ("distal", 1, "distal"),
        ("promoter;gene_body;distal", 3, "mixed"),
    ]
    relationships, count, scope = designs[index % len(designs)]
    shared = f"SYN_REGION_{index // 50:03d}" if index % 50 in {10, 11} else ""
    return relationships, count, scope, shared


def row_for(index: int, definition: dict, design: dict) -> dict[str, str]:
    gene = f"SYN_GENE_{index:04d}"
    truth_class = definition["truth_class"]
    local = index - definition["start"]
    tier = ("EASY", "MODERATE", "HARD")[local % 3]
    effect = design["effect_tiers"][tier]
    magnitude, padj = float(effect["absolute_log2fc"]), float(effect["padj"])
    rna_state = chip_state = "MEASURED"
    rna_observation = chip_observation = "MEASURED"
    rna_direction = chip_direction = "NOT_APPLICABLE"
    rna_lfc = chip_lfc = ""
    rna_padj = chip_padj = ""
    predicted = "ACTIVATION"
    has_peak = True
    expected_pattern = definition["expected_regulatory_pattern"]
    expected_legacy = "DEG_with_differential_peak"
    note = "unambiguous directional pairing"

    if truth_class == "ACTIVATING_CONCORDANT":
        rna_direction, rna_lfc, rna_padj, predicted = "UP", magnitude, padj, "ACTIVATION"
    elif truth_class == "REPRESSIVE_CONCORDANT":
        rna_direction, rna_lfc, rna_padj, predicted = "DOWN", -magnitude, padj, "REPRESSION"
    elif truth_class == "ACTIVATING_DISCORDANT":
        rna_direction, rna_lfc, rna_padj, predicted = "DOWN", -magnitude, padj, "ACTIVATION"
    elif truth_class == "REPRESSIVE_DISCORDANT":
        rna_direction, rna_lfc, rna_padj, predicted = "UP", magnitude, padj, "REPRESSION"
    elif truth_class == "RNA_ONLY":
        rna_direction = "UP" if local % 2 == 0 else "DOWN"
        rna_lfc = magnitude if rna_direction == "UP" else -magnitude
        rna_padj, chip_state, chip_observation, has_peak = padj, "NO_PEAK", "NOT_APPLICABLE", False
        expected_legacy, note = "DEG_only", "significant RNA with measured ChIP peak-gene universe but no peak"
    elif truth_class == "CHIP_ONLY":
        rna_state, rna_observation = "NOT_MEASURED", "NOT_APPLICABLE"
        expected_legacy, predicted, note = "ChIP_only", "ACTIVATION" if local % 2 == 0 else "REPRESSION", "significant ChIP without RNA gene measurement"
    else:
        tier = "HARD"
        magnitude = float(design["effect_tiers"]["BACKGROUND"]["absolute_log2fc"])
        padj = float(design["effect_tiers"]["BACKGROUND"]["padj"])
        rna_direction, rna_lfc, rna_padj = "UP" if local % 2 == 0 else "DOWN", magnitude if local % 2 == 0 else -magnitude, padj
        if local < 100:
            chip_state, chip_observation, has_peak = "NO_PEAK", "NOT_APPLICABLE", False
            expected_pattern, expected_legacy = "NO_REGULATORY_INTERPRETATION", "unchanged"
            note = "RNA measured but not significant and no ChIP peak"
        else:
            expected_pattern, expected_legacy = "INSUFFICIENT_CROSS_ASSAY_EVIDENCE", "ChIP_only"
            predicted = "ACTIVATION" if local % 2 == 0 else "REPRESSION"
            note = "peak present with non-significant RNA and differential binding"

    source_mark = canonical_mark = mark_role = "NOT_APPLICABLE"
    if has_peak:
        source_mark, canonical_mark, mark_role, sign = mark_for(index, predicted)
        chip_direction = "INCREASED" if sign > 0 else "DECREASED"
        chip_lfc = sign * magnitude
        chip_padj = padj
        if truth_class == "NO_CHANGE_BACKGROUND":
            chip_lfc = sign * float(design["effect_tiers"]["BACKGROUND"]["absolute_log2fc"])
            chip_padj = float(design["effect_tiers"]["BACKGROUND"]["padj"])
        if truth_class == "CHIP_ONLY" and local % 25 == 0:
            source_mark, canonical_mark, mark_role = "HP1", "SmHP1", "CONTEXT_DEPENDENT"
        elif truth_class == "CHIP_ONLY" and local % 25 == 1:
            source_mark, canonical_mark, mark_role = "SYNTHETIC_UNKNOWN_MARK", "SYNTHETIC_UNKNOWN_MARK", "UNKNOWN"

    relationships, peak_count, peak_scope, shared_region = peak_design(index, has_peak)
    source_rna, source_chip, normalization = sources(gene, index)
    if rna_state == "NOT_MEASURED":
        source_rna = "NOT_APPLICABLE"
    if chip_state == "NO_PEAK":
        source_chip = gene

    explicit_missing = "NONE"
    if truth_class == "NO_CHANGE_BACKGROUND" and local < 40:
        rna_observation, explicit_missing = "MISSING", "RNA_EXPRESSION_MEASUREMENT"
    elif truth_class == "NO_CHANGE_BACKGROUND" and 100 <= local < 140:
        chip_observation, chip_lfc, explicit_missing = "MISSING", "", "CHIP_DIFFERENTIAL_BINDING_EFFECT"

    source_context = "adults" if index % 50 == 0 else "treated"
    canonical_context = "adult" if source_context == "adults" else "treated"
    priority = "BACKGROUND"
    if truth_class != "NO_CHANGE_BACKGROUND":
        priority = {"EASY": "HIGH", "MODERATE": "MEDIUM", "HARD": "LOW"}[tier]
    context_flags = "gene_of_interest" if index % 100 == 0 else "none"

    return {field: "" for field in FIELDS} | {
        "gene_id": gene,
        "source_rna_gene_id": source_rna,
        "source_chip_gene_id": source_chip,
        "truth_class": truth_class,
        "expected_regulatory_pattern": expected_pattern,
        "expected_legacy_evidence_class": expected_legacy,
        "rna_evidence_state": rna_state,
        "rna_observation_state": rna_observation,
        "rna_direction": rna_direction,
        "rna_log2fc": fmt(rna_lfc),
        "rna_padj": fmt(rna_padj),
        "chip_evidence_state": chip_state,
        "chip_observation_state": chip_observation,
        "source_mark": source_mark,
        "expected_canonical_mark": canonical_mark,
        "mark_role": mark_role,
        "chip_direction": chip_direction,
        "chip_log2fc": fmt(chip_lfc),
        "chip_padj": fmt(chip_padj),
        "peak_relationships": relationships,
        "peak_count": str(peak_count),
        "expected_peak_scope": peak_scope,
        "multi_gene_region_id": shared_region,
        "context_type": "stage" if source_context == "adults" else "condition",
        "source_context": source_context,
        "expected_canonical_context": canonical_context,
        "source_rna_contrast_id": design["contrast"]["rna_contrast_id"] if rna_state != "NOT_MEASURED" else "NOT_APPLICABLE",
        "source_chip_contrast_id": design["contrast"]["chip_contrast_id"] if has_peak else "NOT_APPLICABLE",
        "expected_canonical_contrast_id": design["contrast"]["canonical_contrast_id"],
        "normalization_case": normalization,
        "explicit_missing_observation": explicit_missing,
        "difficulty_tier": tier,
        "candidate_priority": priority,
        "candidate_context_flags": context_flags,
        "truth_note": note,
    }


def generate(design_path: Path, output_dir: Path) -> None:
    design = json.loads(design_path.read_text(encoding="utf-8"))
    definitions = []
    cursor = 1
    for item in design["classes"]:
        definitions.append(item | {"start": cursor})
        cursor += int(item["count"])
    if cursor - 1 != int(design["entity_count"]):
        raise ValueError("class counts do not equal entity_count")

    rows = []
    for definition in definitions:
        for index in range(definition["start"], definition["start"] + int(definition["count"])):
            rows.append(row_for(index, definition, design))

    output_dir.mkdir(parents=True, exist_ok=True)
    truth_path = output_dir / "synthetic_truth.tsv"
    with truth_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    class_counts = {item["truth_class"]: int(item["count"]) for item in design["classes"]}
    manifest = {
        "schema_version": "1.0",
        "type": "integrative_synthetic_truth",
        "id": design["design_id"],
        "status": "frozen",
        "generated_from": str(design_path.as_posix()),
        "generator": "benchmark/integrative/scripts/generate_synthetic_truth.py",
        "imports_helixforge_code": False,
        "seed": design["seed"],
        "entity_count": len(rows),
        "class_counts": class_counts,
        "reference": design["reference"],
        "contrast": design["contrast"],
        "truth_table": {"path": "synthetic_truth.tsv", "sha256": sha256(truth_path)},
        "mutation_policy": "immutable_after_first_helixforge_execution",
        "scientific_execution": "not_started",
    }
    manifest_path = output_dir / "synthetic_truth_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    checksums = [
        f"{sha256(truth_path)}  synthetic_truth.tsv",
        f"{sha256(manifest_path)}  synthetic_truth_manifest.json",
        f"{sha256(design_path)}  ../configs/synthetic_design.json",
    ]
    for name in (
        "dataset_registry.tsv",
        "real_dataset_candidates.tsv",
        "real_integrative_biological_expectations.tsv",
        "negative_contract_cases.tsv",
        "reference_sources.tsv",
    ):
        target = output_dir / name
        if target.is_file():
            checksums.append(f"{sha256(target)}  {name}")
    (output_dir / "SHA256SUMS").write_text("\n".join(checksums) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--design", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    generate(args.design.resolve(), args.output_dir.resolve())


if __name__ == "__main__":
    main()
