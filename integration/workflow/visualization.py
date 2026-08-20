from __future__ import annotations

import html
import json
from collections import Counter
from pathlib import Path
from typing import Any

from integration.evidence.io import read_tsv, safe_id, sha256, write_tsv
from integration.interpretation.scoring import SCORE_COMPONENTS


FIGURE_FIELDS = ["figure_id", "path", "format", "title", "source_datasets", "checksum", "status"]
PANEL_FIELDS = ["canonical_entity_id", "rank", "final_score", "legacy_evidence_class", "regulatory_patterns", "figure"]


def _svg_bars(title: str, labels: list[str], values: list[float], subtitle: str = "") -> str:
    width, height = 900, max(280, 95 + len(labels) * 32)
    maximum = max(values, default=1.0) or 1.0
    rows = []
    for index, (label, value) in enumerate(zip(labels, values)):
        y = 75 + index * 32
        bar_width = 560 * value / maximum
        rows.append(f'<text x="15" y="{y + 16}" font-size="13">{html.escape(str(label)[:42])}</text>')
        rows.append(f'<rect x="285" y="{y}" width="{bar_width:.2f}" height="21" rx="3" fill="#2563eb"/>')
        rows.append(f'<text x="{292 + bar_width:.2f}" y="{y + 16}" font-size="12">{value:.4g}</text>')
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        '<rect width="100%" height="100%" fill="white"/>'
        f'<text x="15" y="28" font-size="20" font-weight="bold">{html.escape(title)}</text>'
        f'<text x="15" y="50" font-size="12" fill="#475569">{html.escape(subtitle)}</text>'
        + "".join(rows) + "</svg>\n"
    )


def _candidate_panel(score: dict[str, str], ranking: dict[str, str]) -> str:
    width, height = 920, 520
    components = [(name.replace("_component", ""), float(score.get(name) or 0)) for name in SCORE_COMPONENTS]
    maximum = max((value for _name, value in components), default=1.0) or 1.0
    bars = []
    for index, (name, value) in enumerate(components):
        x = 25 + (index % 2) * 445
        y = 155 + (index // 2) * 48
        bars.append(f'<text x="{x}" y="{y}" font-size="12">{html.escape(name)}</text>')
        bars.append(f'<rect x="{x}" y="{y + 8}" width="{350 * value / maximum:.2f}" height="18" fill="#0f766e" rx="2"/>')
        bars.append(f'<text x="{x + 360}" y="{y + 23}" font-size="11">{value:.3g}</text>')
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        '<rect width="100%" height="100%" fill="white"/><rect x="8" y="8" width="904" height="504" rx="10" fill="none" stroke="#cbd5e1"/>'
        f'<text x="25" y="42" font-size="23" font-weight="bold">{html.escape(score["canonical_entity_id"])}</text>'
        f'<text x="25" y="72" font-size="15">Rank {html.escape(ranking["rank"])} · score {html.escape(score["final_score"])}</text>'
        f'<text x="25" y="100" font-size="14">{html.escape(score.get("legacy_evidence_class", ""))}</text>'
        f'<text x="25" y="125" font-size="12" fill="#475569">{html.escape(score.get("regulatory_patterns", ""))}</text>'
        + "".join(bars) + "</svg>\n"
    )


def build_visualizations(interpretation_dir: Path, functional_dir: Path, output: Path, panel_count: int = 5) -> dict[str, Any]:
    interpretation = json.loads((interpretation_dir / "interpretation_manifest.json").read_text(encoding="utf-8"))
    functional = json.loads((functional_dir / "functional_manifest.json").read_text(encoding="utf-8"))
    _fields, classes = read_tsv(interpretation_dir / "regulatory_classes.tsv")
    _fields, scores = read_tsv(interpretation_dir / "candidate_score.tsv")
    _fields, ranking = read_tsv(interpretation_dir / "candidate_ranking.tsv")
    output.mkdir(parents=True, exist_ok=True)
    figures: list[dict[str, Any]] = []

    def write_figure(identifier: str, title: str, content: str, sources: str) -> None:
        filename = f"{identifier}.svg"
        (output / filename).write_text(content, encoding="utf-8")
        figures.append({"figure_id": identifier, "path": filename, "format": "svg", "title": title, "source_datasets": sources, "checksum": sha256(output / filename), "status": "created"})

    class_by_gene: dict[str, str] = {}
    for row in classes:
        class_by_gene.setdefault(row.get("canonical_entity_id", ""), row.get("legacy_evidence_class", "unchanged"))
    counts = Counter(class_by_gene.values())
    labels = sorted(counts)
    write_figure("regulatory_class_distribution", "Regulatory-class distribution", _svg_bars("Regulatory-class distribution", labels, [counts[label] for label in labels], "Unique canonical genes"), "regulatory_classes")

    top = ranking[:20]
    write_figure("candidate_ranking", "Top candidate scores", _svg_bars("Top candidate scores", [row["canonical_entity_id"] for row in top], [float(row["final_score"]) for row in top], "Candidate Score v1; non-inferential"), "candidate_ranking;candidate_score")

    coverage = Counter()
    for gene, category in class_by_gene.items():
        if category.startswith("DEG_with_"):
            coverage["RNA + ChIP"] += 1
        elif category == "DEG_only":
            coverage["RNA only"] += 1
        elif category == "ChIP_only":
            coverage["ChIP only"] += 1
        else:
            coverage["No significant integrated evidence"] += 1
    coverage_labels = [name for name in ("RNA + ChIP", "RNA only", "ChIP only", "No significant integrated evidence") if coverage[name]]
    write_figure("evidence_coverage", "Cross-assay evidence coverage", _svg_bars("Cross-assay evidence coverage", coverage_labels, [coverage[name] for name in coverage_labels], "Derived from Regulatory Interpretation Model v1"), "regulatory_classes")

    component_totals = [(name.replace("_component", ""), sum(float(row.get(name) or 0) for row in scores)) for name in SCORE_COMPONENTS]
    write_figure("score_component_decomposition", "Candidate Score component decomposition", _svg_bars("Candidate Score component decomposition", [name for name, _value in component_totals], [value for _name, value in component_totals], "Sum across candidate universe"), "candidate_score")

    enrichment = functional_dir / "functional_enrichment.tsv"
    if enrichment.is_file():
        _fields, terms = read_tsv(enrichment)
        terms = sorted(terms, key=lambda row: (-int(row["n_selected"]), row["term"]))[:20]
        write_figure("functional_terms", "Functional terms among selected candidates", _svg_bars("Functional terms among selected candidates", [row["term"] for row in terms], [float(row["n_selected"]) for row in terms], "Legacy descriptive summary; inferential tests are separate"), "functional_enrichment")

    score_by_gene = {row["canonical_entity_id"]: row for row in scores}
    panel_rows = []
    panel_root = output / "candidate_panels"
    panel_root.mkdir(exist_ok=True)
    for row in ranking[: max(0, panel_count)]:
        gene = row["canonical_entity_id"]
        filename = f"candidate_panels/{safe_id(gene) or 'candidate'}.svg"
        (output / filename).write_text(_candidate_panel(score_by_gene[gene], row), encoding="utf-8")
        figures.append({"figure_id": f"candidate_panel.{gene}", "path": filename, "format": "svg", "title": f"Candidate panel: {gene}", "source_datasets": "candidate_ranking;candidate_score;regulatory_classes", "checksum": sha256(output / filename), "status": "created"})
        panel_rows.append({"canonical_entity_id": gene, "rank": row["rank"], "final_score": row["final_score"], "legacy_evidence_class": row.get("legacy_evidence_class", ""), "regulatory_patterns": row.get("regulatory_patterns", ""), "figure": filename})

    write_tsv(output / "visualization_manifest.tsv", FIGURE_FIELDS, figures)
    write_tsv(output / "candidate_panel_index.tsv", PANEL_FIELDS, panel_rows)
    datasets = [
        {"dataset_id": "visualization.figures", "path": "visualization_manifest.tsv", "records": len(figures), "checksum": {"algorithm": "sha256", "value": sha256(output / "visualization_manifest.tsv")}},
        {"dataset_id": "visualization.candidate_panels", "path": "candidate_panel_index.tsv", "records": len(panel_rows), "checksum": {"algorithm": "sha256", "value": sha256(output / "candidate_panel_index.tsv")}},
    ]
    document = {
        "schema_version": "1.0", "visualization_model_version": "1.0", "type": "integrative_visualization",
        "id": f"{interpretation['id']}.visualization", "status": "complete", "reference": interpretation.get("reference", {}),
        "input_manifests": [
            {"id": interpretation["id"], "checksum": {"algorithm": "sha256", "value": sha256(interpretation_dir / "interpretation_manifest.json")}},
            {"id": functional["id"], "checksum": {"algorithm": "sha256", "value": sha256(functional_dir / "functional_manifest.json")}},
        ],
        "renderer": {"name": "helixforge_svg_v1", "science_recalculated": False, "formats": ["svg"]},
        "datasets": datasets, "record_counts": {"figures": len(figures), "candidate_panels": len(panel_rows)},
        "provenance": {"provider": "integrative_visualization", "provider_version": "1.0"},
    }
    (output / "visualization_manifest.json").write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return document
