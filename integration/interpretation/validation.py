from __future__ import annotations

from pathlib import Path

from integration.evidence.io import read_tsv, sha256

from .scoring import SCORE_COMPONENTS


def validate_manifest(document: dict, root: Path) -> list[str]:
    errors: list[str] = []
    if document.get("type") != "molecular_interpretation":
        errors.append("manifest type must be molecular_interpretation")
    if document.get("status") != "complete":
        errors.append("interpretation manifest must be complete")
    datasets: dict[str, list[dict[str, str]]] = {}
    for item in document.get("datasets", []):
        target = (root / item.get("path", "")).resolve()
        if not target.is_relative_to(root.resolve()) or not target.is_file():
            errors.append(f"missing or escaping dataset {item.get('path')}")
            continue
        rows = read_tsv(target)[1]
        datasets[item["dataset_type"]] = rows
        if len(rows) != item.get("records"):
            errors.append(f"{target.name}: record count mismatch")
        if item.get("checksum", {}).get("value") != sha256(target):
            errors.append(f"{target.name}: checksum mismatch")
    classes = datasets.get("regulatory_classification", [])
    class_ids = [row.get("classification_id") for row in classes]
    if len(class_ids) != len(set(class_ids)):
        errors.append("duplicate regulatory classification ID")
    scores = datasets.get("candidate_score", [])
    score_genes = [row.get("canonical_entity_id") for row in scores]
    if len(score_genes) != len(set(score_genes)):
        errors.append("duplicate candidate score gene")
    for row in scores:
        component_sum = sum(float(row[name]) for name in SCORE_COMPONENTS)
        if abs(component_sum - float(row["final_score"])) > 5e-4:
            errors.append(f"{row.get('canonical_entity_id')}: score components do not sum to final_score")
        if row.get("score_is_inferential") != "false":
            errors.append(f"{row.get('canonical_entity_id')}: candidate score cannot claim inferential meaning")
    rankings = datasets.get("candidate_ranking", [])
    if [int(row.get("rank", 0)) for row in rankings] != list(range(1, len(rankings) + 1)):
        errors.append("candidate ranking is not contiguous")
    ranked_genes = [row.get("canonical_entity_id") for row in rankings]
    if set(ranked_genes) != set(score_genes):
        errors.append("candidate ranking and score gene universes differ")
    for kind in ("fisher_test", "cross_assay_correlation"):
        ids = [row.get("test_id") or row.get("analysis_id") for row in datasets.get(kind, [])]
        if len(ids) != len(set(ids)):
            errors.append(f"duplicate {kind} ID")
    return errors
