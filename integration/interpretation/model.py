from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from integration.evidence.io import sha256

from .common import dataset, load_integration, load_mark_roles, load_policy, number, significant, write_manifest


CLASS_FIELDS = [
    "classification_id", "canonical_entity_id", "reference_id", "canonical_contrast_id", "source_rna_contrast_id", "source_chip_contrast_id", "canonical_mark",
    "mark_regulatory_role", "legacy_evidence_class", "regulatory_pattern", "classification_version",
    "rna_evidence_state", "rna_significance_state", "rna_direction", "rna_effect", "rna_padj",
    "chip_evidence_state", "peak_presence_state", "promoter_peaks", "gene_body_peaks", "distal_peaks",
    "differential_binding_state", "chip_direction", "chip_effect", "chip_padj", "evidence_support",
    "classification_reason", "rna_evidence_ids", "chip_evidence_ids",
]

LEGACY_PRECEDENCE = {
    "DEG_with_differential_peak": 0,
    "DEG_with_promoter_peak": 1,
    "DEG_with_gene_body_peak": 2,
    "DEG_with_distal_peak": 3,
    "DEG_only": 4,
    "ChIP_only": 5,
    "unchanged": 6,
}


def _legacy_class(rna_significant: bool, any_significant_db: bool, promoter: int, body: int, distal: int, total: int) -> str:
    if rna_significant and any_significant_db:
        return "DEG_with_differential_peak"
    if rna_significant and promoter:
        return "DEG_with_promoter_peak"
    if rna_significant and body:
        return "DEG_with_gene_body_peak"
    if rna_significant and distal:
        return "DEG_with_distal_peak"
    if rna_significant:
        return "DEG_only"
    if total:
        return "ChIP_only"
    return "unchanged"


def _regulatory_pattern(rna_state: str, chip_state: str, db_state: str, rna_direction: str, chip_direction: str, role: str) -> tuple[str, str]:
    if rna_state == "NOT_MEASURED":
        return ("CHIP_ONLY", "ChIP evidence exists without an RNA observation") if chip_state == "MEASURED" else ("NO_REGULATORY_INTERPRETATION", "neither assay provides interpretable gene-level evidence")
    if rna_state != "SIGNIFICANT":
        if chip_state == "MEASURED" and db_state == "SIGNIFICANT":
            return "CHIP_ONLY", "differential binding is supported but RNA is not significant"
        if chip_state in {"NO_PEAK", "NOT_MEASURED"}:
            return "NO_REGULATORY_INTERPRETATION", f"RNA is {rna_state.lower()} and ChIP is {chip_state.lower()}"
        return "INSUFFICIENT_CROSS_ASSAY_EVIDENCE", "peak presence without significant differential binding is not a regulatory change"
    if chip_state in {"NO_PEAK", "NOT_MEASURED"}:
        return "RNA_ONLY", f"significant RNA effect with ChIP state {chip_state}"
    if db_state != "SIGNIFICANT":
        return "INSUFFICIENT_CROSS_ASSAY_EVIDENCE", "significant RNA and peak presence lack significant differential binding"
    if role not in {"ACTIVATING", "REPRESSIVE"}:
        return "INSUFFICIENT_MARK_SEMANTICS", f"mark role {role} does not define a directional expectation"
    expected = "UP" if role == "ACTIVATING" and chip_direction == "INCREASED" else None
    if role == "ACTIVATING" and chip_direction == "DECREASED":
        expected = "DOWN"
    elif role == "REPRESSIVE" and chip_direction == "INCREASED":
        expected = "DOWN"
    elif role == "REPRESSIVE" and chip_direction == "DECREASED":
        expected = "UP"
    if expected == rna_direction:
        pattern = "CONCORDANT_ACTIVATION" if rna_direction == "UP" else "CONCORDANT_REPRESSION"
        return pattern, f"{role.lower()} mark {chip_direction.lower()} agrees with RNA {rna_direction.lower()}"
    return "DISCORDANT", f"{role.lower()} mark {chip_direction.lower()} predicts {expected or 'unknown'} but RNA is {rna_direction}"


def build_regulatory_interpretation(integration_dir: Path, policy_path: Path, mark_roles_path: Path, output: Path) -> dict[str, Any]:
    integration, data = load_integration(integration_dir)
    policy = load_policy(policy_path)
    roles = load_mark_roles(mark_roles_path)
    long_rows = data["master_evidence_long"]
    master = {row["canonical_entity_id"]: row for row in data["master_evidence"]}
    aggregations: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: {"total": 0, "promoter": 0, "body": 0, "distal": 0})
    marks_by_gene: dict[str, set[str]] = defaultdict(set)
    peak_assay_measured = bool(data["peak_aggregation"])
    for row in data["peak_aggregation"]:
        key = (row["canonical_entity_id"], row["canonical_mark"])
        aggregations[key]["total"] += int(row["total_associated_peaks"])
        aggregations[key]["promoter"] += int(row["promoter_peaks"])
        aggregations[key]["body"] += int(row["gene_body_peaks"])
        aggregations[key]["distal"] += int(row["distal_peaks"])
        marks_by_gene[row["canonical_entity_id"]].add(row["canonical_mark"])
    de_rows: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    db_rows: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    all_db_by_gene: dict[str, list[dict[str, str]]] = defaultdict(list)
    contrasts_by_gene: dict[str, set[str]] = defaultdict(set)
    for row in long_rows:
        gene, kind = row["canonical_entity_id"], row["evidence_type"]
        if row["entity_type"] != "gene":
            continue
        if kind == "differential_expression":
            de_rows[(gene, row["canonical_contrast_id"])].append(row)
            contrasts_by_gene[gene].add(row["canonical_contrast_id"])
        elif kind == "differential_binding":
            db_rows[(gene, row["canonical_contrast_id"], row["canonical_mark"])].append(row)
            all_db_by_gene[gene].append(row)
            contrasts_by_gene[gene].add(row["canonical_contrast_id"])
            if row["canonical_mark"]:
                marks_by_gene[gene].add(row["canonical_mark"])
    output.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for gene in sorted(master):
        gene_marks = sorted(marks_by_gene.get(gene, set())) or [""]
        contrasts = sorted(filter(None, contrasts_by_gene.get(gene, set()))) or [""]
        gene_peak = {name: sum(values[name] for (item_gene, _mark), values in aggregations.items() if item_gene == gene) for name in ("total", "promoter", "body", "distal")}
        any_significant_db = any(significant(row, policy, "chip") for row in all_db_by_gene.get(gene, []))
        for contrast in contrasts:
            rna_candidates = de_rows.get((gene, contrast), [])
            rna = sorted(rna_candidates, key=lambda row: (number(row.get("padj"), 1.0), -abs(number(row.get("effect"), 0.0))))[0] if rna_candidates else None
            rna_sig = bool(rna and significant(rna, policy, "rna"))
            rna_state = "SIGNIFICANT" if rna_sig else "MEASURED_NOT_SIGNIFICANT" if rna else "NOT_MEASURED"
            rna_effect = number(rna.get("effect")) if rna else None
            rna_direction = "UP" if rna_effect is not None and rna_effect > 0 else "DOWN" if rna_effect is not None and rna_effect < 0 else "UNCHANGED" if rna_effect == 0 else ""
            legacy = _legacy_class(rna_sig, any_significant_db, gene_peak["promoter"], gene_peak["body"], gene_peak["distal"], gene_peak["total"])
            for mark in gene_marks:
                peak = aggregations[(gene, mark)] if mark else {"total": 0, "promoter": 0, "body": 0, "distal": 0}
                candidates = db_rows.get((gene, contrast, mark), [])
                db = sorted(candidates, key=lambda row: (number(row.get("padj"), 1.0), -abs(number(row.get("effect"), 0.0))))[0] if candidates else None
                db_sig = bool(db and significant(db, policy, "chip"))
                db_state = "SIGNIFICANT" if db_sig else "MEASURED_NOT_SIGNIFICANT" if db else "NOT_MEASURED"
                chip_effect = number(db.get("effect")) if db else None
                chip_direction = "INCREASED" if chip_effect is not None and chip_effect > 0 else "DECREASED" if chip_effect is not None and chip_effect < 0 else "UNCHANGED" if chip_effect == 0 else ""
                chip_state = "MEASURED" if peak["total"] or db else master[gene]["chip_evidence_state"]
                role = roles.get(mark, roles.get("unknown", {"regulatory_role": "UNKNOWN"}))["regulatory_role"] if mark else "NOT_APPLICABLE"
                pattern, reason = _regulatory_pattern(rna_state, chip_state, db_state, rna_direction, chip_direction, role)
                support = {
                    "rna": {"effect": rna_effect, "padj": number(rna.get("padj")) if rna else None, "significant": rna_sig},
                    "chip": {"mark": mark or None, "role": role, "peaks": peak["total"], "promoter_peaks": peak["promoter"], "effect": chip_effect, "padj": number(db.get("padj")) if db else None, "significant": db_sig},
                }
                rows.append({
                    "classification_id": f"{gene}|{contrast or 'not_applicable'}|{mark or 'not_applicable'}", "canonical_entity_id": gene,
                    "reference_id": integration["reference"]["reference_id"], "canonical_contrast_id": contrast or "NOT_APPLICABLE",
                    "source_rna_contrast_id": rna.get("source_contrast_id", "") if rna else "", "source_chip_contrast_id": db.get("source_contrast_id", "") if db else "",
                    "canonical_mark": mark or "NOT_APPLICABLE", "mark_regulatory_role": role, "legacy_evidence_class": legacy,
                    "regulatory_pattern": pattern, "classification_version": policy["classification_version"],
                    "rna_evidence_state": master[gene]["rna_evidence_state"], "rna_significance_state": rna_state,
                    "rna_direction": rna_direction, "rna_effect": "" if rna_effect is None else rna_effect, "rna_padj": rna.get("padj", "") if rna else "",
                    "chip_evidence_state": chip_state,
                    "peak_presence_state": "PRESENT" if peak["total"] else "NO_PEAK" if peak_assay_measured else "NOT_MEASURED",
                    "promoter_peaks": peak["promoter"], "gene_body_peaks": peak["body"], "distal_peaks": peak["distal"],
                    "differential_binding_state": db_state, "chip_direction": chip_direction, "chip_effect": "" if chip_effect is None else chip_effect,
                    "chip_padj": db.get("padj", "") if db else "", "evidence_support": json.dumps(support, sort_keys=True, separators=(",", ":")),
                    "classification_reason": reason, "rna_evidence_ids": rna["source_evidence_id"] if rna else "",
                    "chip_evidence_ids": db["source_evidence_id"] if db else "",
                })
    rows.sort(key=lambda row: (row["canonical_entity_id"], row["canonical_contrast_id"], row["canonical_mark"]))
    produced = dataset(output, "regulatory_classification", "regulatory_classes.tsv", CLASS_FIELDS, rows)
    document = {
        "schema_version": "1.0", "component_version": "1.0", "type": "regulatory_interpretation_component",
        "id": f"{integration['id']}.regulatory-interpretation", "status": "complete", "reference": integration["reference"],
        "input_integration_manifest": {"id": integration["id"], "checksum": {"algorithm": "sha256", "value": sha256(Path(integration_dir) / "integration_manifest.json")}},
        "policy_checksum": {"algorithm": "sha256", "value": sha256(policy_path)}, "mark_role_catalog_checksum": {"algorithm": "sha256", "value": sha256(mark_roles_path)},
        "thresholds": {"rna": policy["rna"], "chip": policy["chip"]}, "dataset": produced,
        "record_counts": {"classifications": len(rows)}, "provenance": {"provider": "regulatory_interpretation", "provider_version": "1.0"},
    }
    write_manifest(output / "regulatory_interpretation_manifest.json", document)
    return document
