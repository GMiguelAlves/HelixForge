from __future__ import annotations

import math
import shutil
import statistics as py_statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

from integration.evidence.io import read_json, read_tsv, sha256

from .common import bh_adjust, dataset, format_number, load_context, load_integration, load_mark_roles, load_policy, number, pearson, spearman, truth, write_manifest


FISHER_FIELDS = [
    "test_id", "analysis_family", "target_set", "feature_scope", "canonical_mark", "canonical_context",
    "universe_definition", "universe_genes", "target_genes", "marked_genes", "overlap_genes", "n11", "n10",
    "n01", "n00", "expected_overlap", "fold_enrichment", "odds_ratio", "alternative", "pvalue", "padj",
    "overlap_gene_ids",
]
CORRELATION_FIELDS = [
    "analysis_id", "analysis_family", "canonical_entity_id", "canonical_mark", "contexts", "rna_metric", "chip_metric",
    "method", "n", "correlation", "pvalue", "padj", "inference_status", "correlation_note", "context_values",
]


def _log_choose(n: int, k: int) -> float:
    if k < 0 or k > n:
        return float("-inf")
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def fisher_right_tail(overlap: int, selected_size: int, marked_size: int, universe_size: int) -> float:
    if universe_size <= 0 or selected_size <= 0 or marked_size <= 0 or overlap <= 0:
        return 1.0
    selected_size, marked_size = min(selected_size, universe_size), min(marked_size, universe_size)
    minimum, maximum = max(0, selected_size - (universe_size - marked_size)), min(selected_size, marked_size)
    overlap = max(overlap, minimum)
    if overlap > maximum:
        return 0.0
    denominator = _log_choose(universe_size, selected_size)
    terms = [_log_choose(marked_size, value) + _log_choose(universe_size - marked_size, selected_size - value) - denominator for value in range(overlap, maximum + 1)]
    terms = [value for value in terms if not math.isinf(value)]
    if not terms:
        return 1.0
    largest = max(terms)
    return max(0.0, min(1.0, math.exp(largest) * sum(math.exp(value - largest) for value in terms)))


def _fisher_rows(data: dict[str, list[dict[str, str]]], scores: dict[str, dict[str, str]], context: dict[str, dict[str, str]], policy: dict[str, Any]) -> list[dict[str, Any]]:
    genes = {row["canonical_entity_id"] for row in data["master_evidence"]}
    deg = {gene for gene, row in scores.items() if int(row["rna_significant_contrasts"]) > 0}
    machinery = {gene for gene in genes if truth(context.get(gene, {}).get("is_epigenetic_machinery"))}
    any_peak: dict[tuple[str, str], set[str]] = defaultdict(set)
    promoter_peak: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in data["peak_aggregation"]:
        gene, mark, stage = row["canonical_entity_id"], row["canonical_mark"], row["canonical_context"] or "unknown"
        if int(row["total_associated_peaks"]) > 0:
            any_peak[(stage, mark)].add(gene)
            any_peak[("all_observed_stages", mark)].add(gene)
        if int(row["promoter_peaks"]) > 0:
            promoter_peak[(stage, mark)].add(gene)
            promoter_peak[("all_observed_stages", mark)].add(gene)
    rows: list[dict[str, Any]] = []
    family = policy["statistics"]["fisher_bh_family"]
    for scope, sets in (("any_peak", any_peak), ("promoter_peak", promoter_peak)):
        for (stage, mark), marked in sorted(sets.items()):
            for target_name, target in (("DEG", deg), ("epigenetic_machinery", machinery)):
                if not marked or not target:
                    continue
                overlap = marked & target
                a, b, c = len(overlap), len(target - overlap), len(marked - overlap)
                d = len(genes) - a - b - c
                expected = len(target) * len(marked) / len(genes) if genes else 0.0
                fold = a / expected if expected else 0.0
                odds = ((a + 0.5) * (d + 0.5)) / ((b + 0.5) * (c + 0.5)) if genes else 0.0
                rows.append({
                    "test_id": f"fisher|{target_name}|{scope}|{mark}|{stage}", "analysis_family": family,
                    "target_set": target_name, "feature_scope": scope, "canonical_mark": mark, "canonical_context": stage,
                    "universe_definition": "all_genes_in_master_evidence", "universe_genes": len(genes), "target_genes": len(target),
                    "marked_genes": len(marked), "overlap_genes": a, "n11": a, "n10": b, "n01": c, "n00": d,
                    "expected_overlap": format_number(expected), "fold_enrichment": format_number(fold), "odds_ratio": format_number(odds),
                    "alternative": "greater", "pvalue": format_number(fisher_right_tail(a, len(target), len(marked), len(genes))), "padj": "",
                    "overlap_gene_ids": ";".join(sorted(overlap, key=lambda gene: (-float(scores[gene]["final_score"]), gene))),
                })
    adjusted = bh_adjust([float(row["pvalue"]) for row in rows])
    for row, value in zip(rows, adjusted):
        row["padj"] = format_number(value)
    return sorted(rows, key=lambda row: (float(row["padj"]), float(row["pvalue"]), row["target_set"], row["canonical_mark"], row["canonical_context"]))


def _correlation_rows(data: dict[str, list[dict[str, str]]], policy: dict[str, Any]) -> list[dict[str, Any]]:
    expression: dict[tuple[str, str], list[float]] = defaultdict(list)
    mark_contexts: dict[str, set[str]] = defaultdict(set)
    genes_by_mark: dict[str, set[str]] = defaultdict(set)
    peak_counts: dict[tuple[str, str, str], dict[str, int]] = defaultdict(lambda: {"total": 0, "promoter": 0})
    for row in data["master_evidence_long"]:
        if row["entity_type"] == "gene" and row["evidence_type"] == "expression" and row.get("measurement") and row.get("canonical_context"):
            expression[(row["canonical_entity_id"], row["canonical_context"])].append(float(row["measurement"]))
        if row["source_assay"] == "chipseq" and row.get("canonical_mark") and row.get("canonical_context") and row["canonical_context"] != "all_stages":
            mark_contexts[row["canonical_mark"]].add(row["canonical_context"])
    for row in data["peak_aggregation"]:
        gene, mark, context = row["canonical_entity_id"], row["canonical_mark"], row["canonical_context"]
        if context and context != "all_stages":
            mark_contexts[mark].add(context)
            genes_by_mark[mark].add(gene)
            peak_counts[(gene, mark, context)]["total"] += int(row["total_associated_peaks"])
            peak_counts[(gene, mark, context)]["promoter"] += int(row["promoter_peaks"])
    minimum = int(policy["statistics"]["correlation_min_n"])
    rows: list[dict[str, Any]] = []
    for mark in sorted(genes_by_mark):
        contexts = sorted(mark_contexts[mark])
        for gene in sorted(genes_by_mark[mark]):
            points = []
            for context in contexts:
                values = expression.get((gene, context), [])
                if values:
                    peaks = peak_counts[(gene, mark, context)]
                    points.append((context, py_statistics.mean(values), float(peaks["total"]), float(peaks["promoter"])))
            for chip_metric, position in (("total_associated_peaks", 2), ("promoter_peaks", 3)):
                xs, ys = [point[1] for point in points], [point[position] for point in points]
                for method, value in (("pearson", pearson(xs, ys) if len(points) >= minimum else None), ("spearman", spearman(xs, ys) if len(points) >= minimum else None)):
                    note = "insufficient_n" if len(points) < minimum else "constant_expression_or_chip_signal" if value is None else "low_stage_count" if len(points) < 3 else ""
                    rows.append({
                        "analysis_id": f"correlation|{gene}|{mark}|{chip_metric}|{method}", "analysis_family": "legacy_gene_mark_stage_correlations",
                        "canonical_entity_id": gene, "canonical_mark": mark, "contexts": ";".join(point[0] for point in points),
                        "rna_metric": "mean_TPM", "chip_metric": chip_metric, "method": method, "n": len(points),
                        "correlation": format_number(value), "pvalue": "", "padj": "", "inference_status": "NOT_COMPUTED_LEGACY",
                        "correlation_note": note, "context_values": ";".join(f"{item[0]}:TPM={format_number(item[1])},chip={format_number(item[position])}" for item in points),
                    })
    return sorted(rows, key=lambda row: (row["canonical_entity_id"], row["canonical_mark"], row["chip_metric"], row["method"]))


def build_cross_assay_statistics(integration_dir: Path, classification_dir: Path, scoring_dir: Path, policy_path: Path, mark_roles_path: Path, context_path: Path | None, output: Path) -> dict[str, Any]:
    integration, data = load_integration(integration_dir)
    policy = load_policy(policy_path)
    load_mark_roles(mark_roles_path)
    classes_manifest = read_json(classification_dir / "regulatory_interpretation_manifest.json")
    scoring_manifest = read_json(scoring_dir / "candidate_scoring_manifest.json")
    if classes_manifest.get("input_integration_manifest", {}).get("id") != integration["id"] or scoring_manifest.get("input_integration_manifest", {}).get("id") != integration["id"]:
        raise ValueError("Stage 5 component manifests do not share the same Integration Manifest")
    genes = {row["canonical_entity_id"] for row in data["master_evidence"]}
    context = load_context(context_path, genes)
    score_rows = read_tsv(scoring_dir / "candidate_score.tsv")[1]
    scores = {row["canonical_entity_id"]: row for row in score_rows}
    fisher = _fisher_rows(data, scores, context, policy)
    correlations = _correlation_rows(data, policy)
    output.mkdir(parents=True, exist_ok=True)
    shutil.copy2(classification_dir / "regulatory_classes.tsv", output / "regulatory_classes.tsv")
    shutil.copy2(scoring_dir / "candidate_score.tsv", output / "candidate_score.tsv")
    shutil.copy2(scoring_dir / "candidate_ranking.tsv", output / "candidate_ranking.tsv")
    shutil.copy2(mark_roles_path, output / "mark_role_catalog.tsv")
    produced = [
        {"dataset_type": "regulatory_classification", "path": "regulatory_classes.tsv", "records": len(read_tsv(output / "regulatory_classes.tsv")[1]), "checksum": {"algorithm": "sha256", "value": sha256(output / "regulatory_classes.tsv")}},
        {"dataset_type": "candidate_score", "path": "candidate_score.tsv", "records": len(score_rows), "checksum": {"algorithm": "sha256", "value": sha256(output / "candidate_score.tsv")}},
        {"dataset_type": "candidate_ranking", "path": "candidate_ranking.tsv", "records": len(score_rows), "checksum": {"algorithm": "sha256", "value": sha256(output / "candidate_ranking.tsv")}},
        dataset(output, "fisher_test", "fisher_tests.tsv", FISHER_FIELDS, fisher),
        dataset(output, "cross_assay_correlation", "correlations.tsv", CORRELATION_FIELDS, correlations),
        {"dataset_type": "mark_role_catalog", "path": "mark_role_catalog.tsv", "records": len(read_tsv(output / "mark_role_catalog.tsv")[1]), "checksum": {"algorithm": "sha256", "value": sha256(output / "mark_role_catalog.tsv")}},
    ]
    if context_path:
        shutil.copy2(context_path, output / "prioritization_context.tsv")
        produced.append({"dataset_type": "prioritization_context", "path": "prioritization_context.tsv", "records": len(read_tsv(output / "prioritization_context.tsv")[1]), "checksum": {"algorithm": "sha256", "value": sha256(output / "prioritization_context.tsv")}})
    document = {
        "schema_version": "1.0", "interpretation_model_version": policy["interpretation_model_version"], "classification_version": policy["classification_version"],
        "candidate_score_version": policy["candidate_score_version"], "type": "molecular_interpretation", "id": f"{integration['id']}.interpretation", "status": "complete",
        "reference": integration["reference"], "input_integration_manifest": {"id": integration["id"], "checksum": {"algorithm": "sha256", "value": sha256(Path(integration_dir) / "integration_manifest.json")}},
        "input_component_manifests": [{"id": classes_manifest["id"], "checksum": {"algorithm": "sha256", "value": sha256(classification_dir / "regulatory_interpretation_manifest.json")}}, {"id": scoring_manifest["id"], "checksum": {"algorithm": "sha256", "value": sha256(scoring_dir / "candidate_scoring_manifest.json")}}],
        "policy_checksum": {"algorithm": "sha256", "value": sha256(policy_path)}, "candidate_score": {"version": policy["candidate_score_version"], "semantics": "deterministic_non_inferential_prioritization_heuristic", "formula": policy["score"]},
        "thresholds": {"rna": policy["rna"], "chip": policy["chip"]}, "mark_role_catalog": {"version": "1.0", "checksum": {"algorithm": "sha256", "value": sha256(mark_roles_path)}},
        "prioritization_context": {"status": "provided" if context_path else "not_provided", "checksum": {"algorithm": "sha256", "value": sha256(context_path)} if context_path else None},
        "statistics_methods": {"fisher": {"alternative": "greater", "odds_ratio_correction": "Haldane-Anscombe 0.5", "bh_family": policy["statistics"]["fisher_bh_family"]}, "correlation": {"methods": ["pearson", "spearman"], "minimum_n": policy["statistics"]["correlation_min_n"], "inferential_pvalues": False}},
        "datasets": produced, "record_counts": {"classifications": produced[0]["records"], "scores": len(score_rows), "rankings": len(score_rows), "fisher_tests": len(fisher), "correlations": len(correlations)},
        "provenance": {"provider": "cross_assay_statistics", "provider_version": "1.0", "classification_manifest_id": classes_manifest["id"], "scoring_manifest_id": scoring_manifest["id"]},
    }
    write_manifest(output / "interpretation_manifest.json", document)
    return document
