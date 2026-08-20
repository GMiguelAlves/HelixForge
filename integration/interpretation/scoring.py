from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

from integration.evidence.io import read_json, read_tsv, sha256

from .common import dataset, load_context, load_integration, load_policy, number, significant, truth, write_manifest
from .model import LEGACY_PRECEDENCE


SCORE_COMPONENTS = [
    "deg_significance_component", "rna_log2fc_component", "promoter_peak_component", "differential_peak_component",
    "gene_interest_component", "epigenetic_machinery_component", "multi_contrast_component", "multi_mark_component",
    "wgcna_component", "mfuzz_component", "dtu_component", "splicing_component",
]
SCORE_FIELDS = [
    "canonical_entity_id", "reference_id", "legacy_evidence_class", "regulatory_patterns", *SCORE_COMPONENTS,
    "raw_score", "final_score", "statistical_support", "score_version", "context_status", "score_is_inferential",
    "rna_min_padj", "rna_max_abs_log2fc", "rna_significant_contrasts", "chip_significant_differential_bindings",
    "promoter_peaks", "marks_or_factors", "is_gene_of_interest", "is_epigenetic_machinery", "machinery_group",
    "wgcna_hit", "mfuzz_hit", "dtu_hit", "splicing_hit", "source_rna_evidence_ids", "source_chip_evidence_ids",
]
RANK_FIELDS = [
    "rank", "canonical_entity_id", "final_score", "statistical_support", "legacy_evidence_class",
    "regulatory_patterns", "score_version", "tie_break_rule",
]


def rank_candidates(scores: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ordered = sorted(scores, key=lambda row: (-float(row["final_score"]), -float(row["statistical_support"]), row["canonical_entity_id"]))
    rankings = [{"rank": index, "canonical_entity_id": row["canonical_entity_id"], "final_score": row["final_score"], "statistical_support": row["statistical_support"], "legacy_evidence_class": row["legacy_evidence_class"], "regulatory_patterns": row["regulatory_patterns"], "score_version": row["score_version"], "tie_break_rule": "final_score_desc;statistical_support_desc;canonical_entity_id_asc"} for index, row in enumerate(ordered, 1)]
    return ordered, rankings


def _component_values(gene: str, rows: list[dict[str, str]], peak_rows: list[dict[str, str]], context: dict[str, str], policy: dict[str, Any]) -> dict[str, Any]:
    de = [row for row in rows if row["entity_type"] == "gene" and row["evidence_type"] == "differential_expression"]
    db = [row for row in rows if row["entity_type"] == "gene" and row["evidence_type"] == "differential_binding"]
    padjs = [number(row.get("padj")) for row in de]
    padjs = [value for value in padjs if value is not None]
    effects = [abs(number(row.get("effect"), 0.0)) for row in de]
    min_padj = min(padjs) if padjs else 1.0
    max_lfc = max(effects, default=0.0)
    significant_contrasts = len({row["canonical_contrast_id"] for row in de if significant(row, policy, "rna")})
    significant_db = [row for row in db if significant(row, policy, "chip")]
    promoter = sum(int(row["promoter_peaks"]) for row in peak_rows)
    marks = sorted({row["canonical_mark"] for row in peak_rows if row["canonical_mark"]} | {row["canonical_mark"] for row in db if row["canonical_mark"]})
    settings = policy["score"]
    components = {
        "deg_significance_component": min(float(settings["deg_significance_cap"]), -math.log10(max(min_padj, 1e-300))) if min_padj < 1 else 0.0,
        "rna_log2fc_component": min(float(settings["rna_log2fc_cap"]), max_lfc),
        "promoter_peak_component": float(settings["promoter_peak_bonus"]) if promoter > 0 else 0.0,
        "differential_peak_component": float(settings["differential_peak_bonus"]) if significant_db else 0.0,
        "gene_interest_component": float(settings["gene_interest_bonus"]) if truth(context.get("is_gene_of_interest")) else 0.0,
        "epigenetic_machinery_component": float(settings["epigenetic_machinery_bonus"]) if truth(context.get("is_epigenetic_machinery")) else 0.0,
        "multi_contrast_component": min(float(settings["significant_contrast_cap"]), significant_contrasts * float(settings["significant_contrast_increment"])),
        "multi_mark_component": min(float(settings["mark_cap"]), len(marks) * float(settings["mark_increment"])),
        "wgcna_component": float(settings["wgcna_bonus"]) if truth(context.get("wgcna_hit")) else 0.0,
        "mfuzz_component": float(settings["mfuzz_bonus"]) if truth(context.get("mfuzz_hit")) else 0.0,
        "dtu_component": float(settings["dtu_bonus"]) if truth(context.get("dtu_hit")) else 0.0,
        "splicing_component": float(settings["splicing_bonus"]) if truth(context.get("splicing_hit")) else 0.0,
    }
    return {"components": components, "min_padj": min_padj, "max_lfc": max_lfc, "significant_contrasts": significant_contrasts, "significant_db": significant_db, "promoter": promoter, "marks": marks, "de": de, "db": db}


def build_candidate_scores(integration_dir: Path, classification_dir: Path, policy_path: Path, context_path: Path | None, output: Path) -> dict[str, Any]:
    integration, data = load_integration(integration_dir)
    policy = load_policy(policy_path)
    class_manifest = read_json(classification_dir / "regulatory_interpretation_manifest.json")
    if class_manifest.get("input_integration_manifest", {}).get("id") != integration["id"]:
        raise ValueError("classification and integration manifests do not share the same input")
    classes = read_tsv(classification_dir / "regulatory_classes.tsv")[1]
    genes = {row["canonical_entity_id"] for row in data["master_evidence"]}
    context = load_context(context_path, genes)
    long_by_gene: dict[str, list[dict[str, str]]] = defaultdict(list)
    peak_by_gene: dict[str, list[dict[str, str]]] = defaultdict(list)
    class_by_gene: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in data["master_evidence_long"]:
        if row["entity_type"] == "gene":
            long_by_gene[row["canonical_entity_id"]].append(row)
    for row in data["peak_aggregation"]:
        peak_by_gene[row["canonical_entity_id"]].append(row)
    for row in classes:
        class_by_gene[row["canonical_entity_id"]].append(row)
    scores: list[dict[str, Any]] = []
    for gene in sorted(genes):
        details = _component_values(gene, long_by_gene[gene], peak_by_gene[gene], context.get(gene, {}), policy)
        components = details["components"]
        final_score = sum(components.values())
        class_rows = class_by_gene[gene]
        legacy = min((row["legacy_evidence_class"] for row in class_rows), key=lambda value: LEGACY_PRECEDENCE[value])
        patterns = sorted({row["regulatory_pattern"] for row in class_rows})
        item: dict[str, Any] = {
            "canonical_entity_id": gene, "reference_id": integration["reference"]["reference_id"], "legacy_evidence_class": legacy,
            "regulatory_patterns": ";".join(patterns), **{name: f"{components[name]:.4f}" for name in SCORE_COMPONENTS},
            "raw_score": f"{final_score:.4f}", "final_score": f"{final_score:.4f}",
            "statistical_support": f"{components['deg_significance_component'] + components['differential_peak_component']:.4f}",
            "score_version": policy["candidate_score_version"], "context_status": "PROVIDED" if gene in context else "NOT_PROVIDED",
            "score_is_inferential": "false", "rna_min_padj": details["min_padj"], "rna_max_abs_log2fc": details["max_lfc"],
            "rna_significant_contrasts": details["significant_contrasts"], "chip_significant_differential_bindings": len(details["significant_db"]),
            "promoter_peaks": details["promoter"], "marks_or_factors": ";".join(details["marks"]),
            "is_gene_of_interest": str(truth(context.get(gene, {}).get("is_gene_of_interest"))).lower(),
            "is_epigenetic_machinery": str(truth(context.get(gene, {}).get("is_epigenetic_machinery"))).lower(),
            "machinery_group": context.get(gene, {}).get("machinery_group", ""),
            "wgcna_hit": str(truth(context.get(gene, {}).get("wgcna_hit"))).lower(), "mfuzz_hit": str(truth(context.get(gene, {}).get("mfuzz_hit"))).lower(),
            "dtu_hit": str(truth(context.get(gene, {}).get("dtu_hit"))).lower(), "splicing_hit": str(truth(context.get(gene, {}).get("splicing_hit"))).lower(),
            "source_rna_evidence_ids": ";".join(sorted({row["source_evidence_id"] for row in details["de"]})),
            "source_chip_evidence_ids": ";".join(sorted({row["source_evidence_id"] for row in details["db"]})),
        }
        scores.append(item)
    scores, rankings = rank_candidates(scores)
    output.mkdir(parents=True, exist_ok=True)
    datasets = [dataset(output, "candidate_score", "candidate_score.tsv", SCORE_FIELDS, scores), dataset(output, "candidate_ranking", "candidate_ranking.tsv", RANK_FIELDS, rankings)]
    document = {
        "schema_version": "1.0", "component_version": "1.0", "type": "candidate_scoring_component", "id": f"{integration['id']}.candidate-scoring",
        "status": "complete", "reference": integration["reference"], "input_integration_manifest": {"id": integration["id"], "checksum": {"algorithm": "sha256", "value": sha256(Path(integration_dir) / "integration_manifest.json")}},
        "input_classification_manifest": {"id": class_manifest["id"], "checksum": {"algorithm": "sha256", "value": sha256(classification_dir / "regulatory_interpretation_manifest.json")}},
        "policy_checksum": {"algorithm": "sha256", "value": sha256(policy_path)}, "context": {"status": "provided" if context_path else "not_provided", "checksum": {"algorithm": "sha256", "value": sha256(context_path)} if context_path else None},
        "candidate_score_version": policy["candidate_score_version"], "score_formula": policy["score"], "score_semantics": "deterministic_non_inferential_prioritization_heuristic",
        "datasets": datasets, "record_counts": {"scores": len(scores), "ranked_candidates": len(rankings)}, "provenance": {"provider": "candidate_scoring", "provider_version": "1.0"},
    }
    write_manifest(output / "candidate_scoring_manifest.json", document)
    return document
