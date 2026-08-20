from __future__ import annotations

import html
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from integration.evidence.io import read_tsv, sha256, write_tsv
from integration.interpretation.model import LEGACY_PRECEDENCE


EXPLORER_FIELDS = [
    "rank", "canonical_entity_id", "legacy_evidence_class", "regulatory_patterns", "final_score",
    "rna_effect", "rna_padj", "marks_or_factors", "peak_positions", "differential_binding",
    "functional_annotations", "source_rna_evidence_ids", "source_chip_evidence_ids",
]


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _table(rows: list[dict[str, Any]], columns: list[str], table_id: str = "") -> str:
    if not rows:
        return '<p class="muted">No records available for this execution.</p>'
    head = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(column, '')))}</td>" for column in columns) + "</tr>"
        for row in rows
    )
    identifier = f' id="{table_id}"' if table_id else ""
    return f'<div class="table-wrap"><table{identifier}><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def _dataset(path: Path, identifier: str, relative: str, records: int) -> dict[str, Any]:
    return {"dataset_id": identifier, "path": relative, "format": path.suffix.lstrip("."), "records": records, "checksum": {"algorithm": "sha256", "value": sha256(path)}}


def build_report(input_dir: Path, rna_evidence_dir: Path, chip_evidence_dir: Path, harmonization_dir: Path, integration_dir: Path, interpretation_dir: Path, functional_dir: Path, visualization_dir: Path, output: Path, title: str) -> dict[str, Any]:
    validation = _load(input_dir / "input_validation.json")
    rna_evidence = _load(rna_evidence_dir / "evidence_manifest.json")
    chip_evidence = _load(chip_evidence_dir / "evidence_manifest.json")
    harmonization = _load(harmonization_dir / "harmonization_manifest.json")
    integration = _load(integration_dir / "integration_manifest.json")
    interpretation = _load(interpretation_dir / "interpretation_manifest.json")
    functional = _load(functional_dir / "functional_manifest.json")
    visualization = _load(visualization_dir / "visualization_manifest.json")
    _fields, scores = read_tsv(interpretation_dir / "candidate_score.tsv")
    _fields, ranking = read_tsv(interpretation_dir / "candidate_ranking.tsv")
    _fields, classes = read_tsv(interpretation_dir / "regulatory_classes.tsv")
    _fields, fisher = read_tsv(interpretation_dir / "fisher_tests.tsv")
    _fields, correlations = read_tsv(interpretation_dir / "correlations.tsv")
    _fields, figures = read_tsv(visualization_dir / "visualization_manifest.tsv")
    functional_rows = read_tsv(functional_dir / "functional_enrichment.tsv")[1] if (functional_dir / "functional_enrichment.tsv").is_file() else []

    classes_by_gene: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in classes:
        classes_by_gene[row["canonical_entity_id"]].append(row)
    scores_by_gene = {row["canonical_entity_id"]: row for row in scores}
    terms_by_gene: dict[str, set[str]] = defaultdict(set)
    for row in functional_rows:
        for gene in row.get("selected_genes", "").split(";"):
            if gene:
                terms_by_gene[gene].add(row["term"])
    explorer = []
    for ranked in ranking:
        gene = ranked["canonical_entity_id"]
        score = scores_by_gene[gene]
        gene_classes = classes_by_gene[gene]
        representative = min(gene_classes, key=lambda row: LEGACY_PRECEDENCE[row["legacy_evidence_class"]]) if gene_classes else {}
        marks = sorted({row["canonical_mark"] for row in gene_classes if row.get("canonical_mark") not in {"", "NOT_APPLICABLE"}})
        positions = []
        if any(int(row.get("promoter_peaks") or 0) for row in gene_classes):
            positions.append("promoter")
        if any(int(row.get("gene_body_peaks") or 0) for row in gene_classes):
            positions.append("gene_body")
        if any(int(row.get("distal_peaks") or 0) for row in gene_classes):
            positions.append("distal")
        explorer.append({
            "rank": ranked["rank"], "canonical_entity_id": gene,
            "legacy_evidence_class": representative.get("legacy_evidence_class", ranked.get("legacy_evidence_class", "")),
            "regulatory_patterns": ranked.get("regulatory_patterns", ""), "final_score": ranked["final_score"],
            "rna_effect": representative.get("rna_effect", ""), "rna_padj": representative.get("rna_padj", ""),
            "marks_or_factors": ";".join(marks), "peak_positions": ";".join(positions),
            "differential_binding": "significant" if any(row.get("differential_binding_state") == "SIGNIFICANT" for row in gene_classes) else "not_significant_or_not_measured",
            "functional_annotations": ";".join(sorted(terms_by_gene[gene])),
            "source_rna_evidence_ids": score.get("source_rna_evidence_ids", ""), "source_chip_evidence_ids": score.get("source_chip_evidence_ids", ""),
        })
    output.mkdir(parents=True, exist_ok=True)
    write_tsv(output / "candidate_explorer.tsv", EXPLORER_FIELDS, explorer)

    class_counts = Counter(row["legacy_evidence_class"] for row in {gene: min(rows, key=lambda value: LEGACY_PRECEDENCE[value["legacy_evidence_class"]]) for gene, rows in classes_by_gene.items()}.values())
    method_rows = [
        ("Integration API", "1.0"), ("Evidence Model", rna_evidence.get("evidence_model_version", "unknown")),
        ("Harmonization", harmonization.get("harmonization_model_version", "unknown")),
        ("Integration Model", integration.get("integration_model_version", "unknown")),
        ("Interpretation Model", interpretation.get("interpretation_model_version", "unknown")),
        ("Candidate Score", interpretation.get("candidate_score_version", "unknown")),
        ("Functional Model", functional.get("functional_model_version", "unknown")),
    ]
    methods = "\n".join(f"- {name}: {version}" for name, version in method_rows)
    markdown = (
        f"# {title}\n\n"
        f"## Overview\n\n- Integrated genes: {len(explorer)}\n- Fisher tests: {len(fisher)}\n- Correlations: {len(correlations)}\n- Functional terms: {functional.get('record_counts', {}).get('terms', 0)}\n\n"
        "## Methods and versions\n\n" + methods + "\n\n"
        "Candidate Score v1 is a deterministic prioritization heuristic and is not an inferential statistic.\n"
    )
    (output / "integrative_report.md").write_text(markdown, encoding="utf-8")

    figure_cards = []
    for figure in figures:
        path = visualization_dir / figure["path"]
        if path.is_file() and path.suffix == ".svg" and not figure["path"].startswith("candidate_panels/"):
            figure_cards.append(f'<figure>{path.read_text(encoding="utf-8")}<figcaption>{html.escape(figure["title"])}</figcaption></figure>')
    class_rows = [{"class": name, "genes": count} for name, count in sorted(class_counts.items(), key=lambda item: (LEGACY_PRECEDENCE[item[0]], item[0]))]
    method_table = [{"component": name, "version": version} for name, version in method_rows]
    input_rows = [{"assay": item["assay"], "manifest": item["manifest_id"], "checksum": item["manifest_checksum"], "bound_artifacts": item["bound_artifacts"]} for item in validation["inputs"]]
    html_text = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><style>
body{{font-family:Arial,sans-serif;margin:0;background:#f8fafc;color:#0f172a}}header{{background:#0f172a;color:white;padding:28px}}main{{max-width:1280px;margin:auto;padding:22px}}section{{background:white;border:1px solid #e2e8f0;border-radius:9px;padding:18px;margin:0 0 18px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:14px}}figure{{margin:0;border:1px solid #e2e8f0;padding:8px;border-radius:7px}}figure svg{{width:100%;height:auto}}figcaption{{font-size:13px;color:#475569}}.table-wrap{{overflow:auto}}table{{border-collapse:collapse;width:100%;font-size:12px}}th,td{{padding:7px;border-bottom:1px solid #e2e8f0;text-align:left;white-space:nowrap}}th{{background:#f1f5f9}}input{{padding:9px;width:min(480px,90%);margin-bottom:10px}}.muted{{color:#64748b}}
</style></head><body><header><h1>{html.escape(title)}</h1><p>Structured molecular evidence, regulatory interpretation and explainable prioritization.</p></header><main>
<section><h2>Overview</h2><div class="grid"><div><strong>{len(explorer)}</strong><br>candidate genes</div><div><strong>{len(fisher)}</strong><br>cross-assay Fisher tests</div><div><strong>{len(correlations)}</strong><br>correlations</div><div><strong>{functional.get('record_counts', {}).get('terms', 0)}</strong><br>functional terms</div></div></section>
<section><h2>Input provenance and compatibility</h2><p>Reference compatibility: <strong>{html.escape(validation['reference_compatibility'])}</strong></p>{_table(input_rows, ['assay','manifest','checksum','bound_artifacts'])}</section>
<section><h2>Cross-assay evidence coverage and regulatory interpretation</h2>{_table(class_rows, ['class','genes'])}</section>
<section><h2>Candidate prioritization</h2><p class="muted">Candidate Score v1 is deterministic and non-inferential.</p><input id="candidate-search" placeholder="Search candidate evidence" oninput="filterCandidates()">{_table(explorer, EXPLORER_FIELDS, 'candidate-explorer')}</section>
<section><h2>Cross-assay statistics</h2><h3>Fisher tests</h3>{_table(fisher[:50], list(fisher[0]) if fisher else [])}<h3>Correlations</h3>{_table(correlations[:50], list(correlations[0]) if correlations else [])}</section>
<section><h2>Functional analysis</h2><p>The legacy descriptive table is preserved; formal Fisher/BH results are stored separately.</p>{_table(functional_rows, list(functional_rows[0]) if functional_rows else [])}</section>
<section><h2>Visualizations</h2><div class="grid">{''.join(figure_cards)}</div></section>
<section><h2>Methods and software provenance</h2>{_table(method_table, ['component','version'])}<p>RNA/ChIP thresholds and the complete Candidate Score formula are recorded in the Interpretation Manifest. Functional terms do not modify Candidate Score v1.</p></section>
</main><script>function filterCandidates(){{const q=document.getElementById('candidate-search').value.toLowerCase();document.querySelectorAll('#candidate-explorer tbody tr').forEach(r=>r.style.display=r.innerText.toLowerCase().includes(q)?'':'none');}}</script></body></html>'''
    (output / "integrative_report.html").write_text(html_text, encoding="utf-8")
    datasets = [
        _dataset(output / "candidate_explorer.tsv", "report.candidate_explorer", "candidate_explorer.tsv", len(explorer)),
        _dataset(output / "integrative_report.md", "report.markdown", "integrative_report.md", 1),
        _dataset(output / "integrative_report.html", "report.html", "integrative_report.html", 1),
    ]
    document = {
        "schema_version": "1.0", "report_model_version": "1.0", "type": "integrative_report",
        "id": f"{interpretation['id']}.report", "status": "complete", "title": title,
        "reference": interpretation.get("reference", {}), "science_recalculated": False,
        "input_manifests": [rna_evidence["id"], chip_evidence["id"], harmonization["id"], integration["id"], interpretation["id"], functional["id"], visualization["id"]],
        "sections": ["overview", "input_provenance", "reference_compatibility", "evidence_coverage", "regulatory_interpretation", "candidate_prioritization", "score_decomposition", "cross_assay_statistics", "functional_analysis", "visualizations", "methods", "provenance"],
        "datasets": datasets, "record_counts": {"candidate_explorer": len(explorer)},
        "provenance": {"provider": "integrative_report", "provider_version": "1.0"},
    }
    (output / "report_manifest.json").write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return document
