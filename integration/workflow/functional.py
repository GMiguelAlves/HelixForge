from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from integration.evidence.io import read_tsv, sha256, write_tsv
from integration.interpretation.common import bh_adjust
from integration.interpretation.statistics import fisher_right_tail


LEGACY_FIELDS = ["term", "n_selected", "n_background", "selected_genes", "note"]
TEST_FIELDS = ["test_id", "term", "tested_gene_set", "background_gene_set", "n11", "n10", "n01", "n00", "odds_ratio", "pvalue", "padj", "method", "alternative", "multiple_testing_family"]
GENE_SET_FIELDS = ["gene_set_id", "canonical_entity_id", "membership", "rank"]
SUMMARY_FIELDS = ["term", "annotated_genes", "selected_genes", "background_size", "selected_size"]


def _dataset(root: Path, identifier: str, filename: str, rows: list[dict[str, Any]], fields: list[str]) -> dict[str, Any]:
    path = root / filename
    write_tsv(path, fields, rows)
    return {"dataset_id": identifier, "path": filename, "format": "tsv", "records": len(rows), "checksum": {"algorithm": "sha256", "value": sha256(path)}}


def _odds(a: int, b: int, c: int, d: int) -> float:
    return ((a + 0.5) * (d + 0.5)) / ((b + 0.5) * (c + 0.5))


def build_functional_analysis(interpretation_dir: Path, annotation_path: Path, top_n: int, output: Path) -> dict[str, Any]:
    interpretation = json.loads((interpretation_dir / "interpretation_manifest.json").read_text(encoding="utf-8"))
    score_fields, scores = read_tsv(interpretation_dir / "candidate_score.tsv")
    _rank_fields, ranking = read_tsv(interpretation_dir / "candidate_ranking.tsv")
    if "canonical_entity_id" not in score_fields:
        raise ValueError("candidate_score.tsv has no canonical_entity_id")
    universe = {row["canonical_entity_id"] for row in scores if row.get("canonical_entity_id")}
    ordered = [row["canonical_entity_id"] for row in ranking if row.get("canonical_entity_id") in universe]
    selected_order = ordered[: max(0, top_n)]
    selected = set(selected_order)
    output.mkdir(parents=True, exist_ok=True)

    annotation_fields, annotation_rows = read_tsv(annotation_path)
    gene_column = next((name for name in ("gene_id", "canonical_entity_id", "gene") if name in annotation_fields), None)
    term_column = next((name for name in ("term", "pathway", "go", "kegg", "functional_annotation") if name in annotation_fields), None)
    terms: dict[str, set[str]] = defaultdict(set)
    if annotation_rows and (not gene_column or not term_column):
        raise ValueError("functional annotation requires gene_id and term columns")
    for row in annotation_rows:
        gene = row.get(gene_column or "", "").strip()
        if gene not in universe:
            continue
        for term in re.split(r"[;,|]", row.get(term_column or "", "")):
            if term.strip():
                terms[term.strip()].add(gene)

    datasets = []
    gene_sets = [
        {"gene_set_id": "experimental_background", "canonical_entity_id": gene, "membership": "background", "rank": ""}
        for gene in sorted(universe)
    ] + [
        {"gene_set_id": "top_ranked_candidates", "canonical_entity_id": gene, "membership": "selected", "rank": index}
        for index, gene in enumerate(selected_order, 1)
    ]
    datasets.append(_dataset(output, "functional.gene_sets", "gene_sets.tsv", gene_sets, GENE_SET_FIELDS))

    legacy_rows, test_rows, summary_rows = [], [], []
    universe_size, selected_size = len(universe), len(selected)
    for term in sorted(terms):
        annotated = terms[term]
        overlap = selected & annotated
        if overlap:
            legacy_rows.append({"term": term, "n_selected": len(overlap), "n_background": len(annotated), "selected_genes": ";".join(sorted(overlap)), "note": "descriptive_count_offline"})
        a = len(overlap)
        b = selected_size - a
        c = len(annotated - selected)
        d = universe_size - a - b - c
        pvalue = fisher_right_tail(a, selected_size, len(annotated), universe_size) if universe_size else 1.0
        test_rows.append({"test_id": f"top_ranked_candidates|{term}", "term": term, "tested_gene_set": "top_ranked_candidates", "background_gene_set": "experimental_background", "n11": a, "n10": b, "n01": c, "n00": d, "odds_ratio": _odds(a, b, c, d), "pvalue": pvalue, "padj": 1.0, "method": "fisher_exact", "alternative": "greater", "multiple_testing_family": "functional_terms_v1"})
        summary_rows.append({"term": term, "annotated_genes": ";".join(sorted(annotated)), "selected_genes": ";".join(sorted(overlap)), "background_size": universe_size, "selected_size": selected_size})
    adjusted = bh_adjust([float(row["pvalue"]) for row in test_rows])
    for row, value in zip(test_rows, adjusted):
        row["padj"] = value
    if terms:
        datasets.extend([
            _dataset(output, "functional.legacy_summary", "functional_enrichment.tsv", legacy_rows, LEGACY_FIELDS),
            _dataset(output, "functional.tests", "functional_tests.tsv", test_rows, TEST_FIELDS),
            _dataset(output, "functional.annotation_summary", "annotation_summary.tsv", summary_rows, SUMMARY_FIELDS),
        ])
    document = {
        "schema_version": "1.0", "functional_model_version": "1.0", "type": "functional_analysis",
        "id": f"{interpretation['id']}.functional", "status": "complete" if terms else "complete_empty",
        "reference": interpretation.get("reference", {}),
        "input_interpretation_manifest": {"id": interpretation["id"], "checksum": {"algorithm": "sha256", "value": sha256(interpretation_dir / "interpretation_manifest.json")}},
        "annotation": {"checksum": {"algorithm": "sha256", "value": sha256(annotation_path)}, "gene_column": gene_column, "term_column": term_column},
        "selection": {"gene_set": "top_ranked_candidates", "top_n": top_n, "selected_genes": selected_size, "background": "all genes in Candidate Score v1", "background_genes": universe_size},
        "methods": {"legacy_summary": "descriptive_count_offline", "formal_test": "right_tailed_fisher_exact", "multiple_testing": "Benjamini-Hochberg across functional terms"},
        "datasets": datasets, "record_counts": {"terms": len(terms), "legacy_rows": len(legacy_rows), "tests": len(test_rows)},
        "provenance": {"provider": "functional_analysis", "provider_version": "1.0"},
    }
    (output / "functional_manifest.json").write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return document
