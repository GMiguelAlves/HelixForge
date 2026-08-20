from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from integration.evidence.io import optional_number, read_json, read_tsv, safe_id, sha256, write_tsv
from integration.harmonization.core import canonical_context, load_evidence_bundle, reference_errors


LONG_FIELDS = [
    "observation_id", "canonical_entity_id", "entity_type", "reference_id", "source_assay", "evidence_type",
    "source_evidence_id", "source_entity_id", "source_artifact_id", "context_type", "source_context", "canonical_context",
    "source_contrast_id", "canonical_contrast_id", "source_mark", "canonical_mark", "measurement", "unit", "effect",
    "direction", "pvalue", "padj", "peak_id", "peak_relationship", "distance_to_tss", "position", "measurement_state",
]
MASTER_FIELDS = [
    "canonical_entity_id", "reference_id", "rna_evidence_state", "chip_evidence_state", "expression_observations",
    "differential_expression_observations", "peak_associations", "differential_binding_observations", "marks_or_factors",
    "contexts", "canonical_contrasts", "rna_evidence_ids", "chip_evidence_ids",
]
PEAK_AGG_FIELDS = [
    "canonical_entity_id", "canonical_mark", "canonical_context", "total_associated_peaks", "promoter_peaks",
    "gene_body_peaks", "distal_peaks", "peak_ids", "source_evidence_ids",
]


def _read_map(root: Path, filename: str) -> list[dict[str, str]]:
    path = (root / filename).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError(f"missing harmonization dataset {filename}")
    return read_tsv(path)[1]


def _lookups(harmonization_dir: Path):
    entity_rows = _read_map(harmonization_dir, "entity_map.tsv")
    contrast_rows = _read_map(harmonization_dir, "contrast_map.tsv")
    mark_rows = _read_map(harmonization_dir, "mark_map.tsv")
    entities = {(row["source_assay"], row["source_entity_id"]): row["canonical_entity_id"] for row in entity_rows}
    contrasts: dict[tuple[str, str], str] = {}
    for row in contrast_rows:
        for source in filter(None, row["rna_contrast_ids"].split(";")):
            contrasts[("rnaseq", source)] = row["canonical_contrast_id"]
        for source in filter(None, row["chip_contrast_ids"].split(";")):
            contrasts[("chipseq", source)] = row["canonical_contrast_id"]
    marks = {row["source_mark"]: row["canonical_mark"] for row in mark_rows}
    return entity_rows, entities, contrasts, marks


def _direction(value: str, assay: str) -> str:
    if value == "":
        return ""
    number = float(value)
    if number == 0:
        return "UNCHANGED"
    if assay == "rnaseq":
        return "UP" if number > 0 else "DOWN"
    return "INCREASED" if number > 0 else "DECREASED"


def _context(row: dict[str, str]) -> tuple[str, str, str]:
    if row.get("stage"):
        source, kind = row["stage"], "stage"
    elif row.get("condition"):
        source, kind = row["condition"], "condition"
    else:
        return "NOT_APPLICABLE", "", ""
    return kind, source, canonical_context(source)[0]


def _base_row(assay: str, kind: str, row: dict[str, str], reference_id: str, canonical_entity: str, entity_type: str, contrasts: dict[tuple[str, str], str], marks: dict[str, str], suffix: str = "") -> dict[str, str]:
    context_type, source_context, canonical_value = _context(row)
    source_contrast = row.get("contrast_id", "")
    source_mark = row.get("mark_or_factor", "")
    effect = row.get("log2_fold_change", "") if kind in {"differential_expression", "differential_binding"} else ""
    measurement = row.get("measurement", "") if kind == "expression" else ""
    state = "MISSING" if (kind == "expression" and not measurement) or (kind in {"differential_expression", "differential_binding"} and not effect) else "MEASURED"
    position = ""
    if row.get("chromosome") and row.get("start") and row.get("end"):
        position = f"{row['chromosome']}:{row['start']}-{row['end']}"
    return {
        "observation_id": f"integrated.{safe_id(row['evidence_id'])}{suffix}", "canonical_entity_id": canonical_entity,
        "entity_type": entity_type, "reference_id": reference_id, "source_assay": assay, "evidence_type": kind,
        "source_evidence_id": row["evidence_id"], "source_entity_id": row.get("source_entity_id", ""),
        "source_artifact_id": row.get("source_artifact_id", ""), "context_type": context_type,
        "source_context": source_context, "canonical_context": canonical_value, "source_contrast_id": source_contrast,
        "canonical_contrast_id": contrasts.get((assay, source_contrast), ""), "source_mark": source_mark,
        "canonical_mark": marks.get(source_mark, source_mark), "measurement": measurement, "unit": row.get("unit", ""),
        "effect": effect, "direction": _direction(effect, assay) if effect else "", "pvalue": row.get("pvalue", ""),
        "padj": row.get("padj", ""), "peak_id": row.get("peak_id", ""),
        "peak_relationship": row.get("relationship", row.get("position_class", "")), "distance_to_tss": row.get("distance_to_tss", ""),
        "position": position, "measurement_state": state,
    }


def _build_long(rna: dict[str, list[dict[str, str]]], chip: dict[str, list[dict[str, str]]], reference_id: str, entities: dict[tuple[str, str], str], contrasts: dict[tuple[str, str], str], marks: dict[str, str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    peak_to_genes: dict[str, list[str]] = defaultdict(list)
    peak_positions: dict[str, str] = {}
    known_peaks: set[str] = set()
    for kind in ("peak", "consensus"):
        for row in chip.get(kind, []):
            known_peaks.add(row["peak_id"])
            if row.get("chromosome") and row.get("start") and row.get("end"):
                peak_positions[row["peak_id"]] = f"{row['chromosome']}:{row['start']}-{row['end']}"
    for row in chip.get("peak_gene", []):
        if known_peaks and row["peak_id"] not in known_peaks:
            raise ValueError(f"peak-gene evidence {row['evidence_id']} references unknown peak {row['peak_id']}")
        canonical = entities.get(("chipseq", row["source_entity_id"]))
        if not canonical:
            raise ValueError(f"cannot reconcile ChIP entity {row['source_entity_id']!r}")
        peak_to_genes[row["peak_id"]].append(canonical)
        integrated = _base_row("chipseq", "peak_gene", row, reference_id, canonical, "gene", contrasts, marks)
        if not integrated["position"]:
            integrated["position"] = peak_positions.get(row["peak_id"], "")
        rows.append(integrated)
    for kind in ("expression", "differential_expression"):
        for row in rna.get(kind, []):
            canonical = entities.get(("rnaseq", row["source_entity_id"]))
            if not canonical:
                raise ValueError(f"cannot reconcile RNA entity {row['source_entity_id']!r}")
            rows.append(_base_row("rnaseq", kind, row, reference_id, canonical, "gene", contrasts, marks))
    for kind in ("peak", "consensus"):
        for row in chip.get(kind, []):
            canonical = f"region:{reference_id}:{row['peak_id']}"
            rows.append(_base_row("chipseq", kind, row, reference_id, canonical, "region", contrasts, marks))
    for row in chip.get("differential_binding", []):
        canonical_gene = entities.get(("chipseq", row.get("source_entity_id", ""))) if row.get("source_entity_id") else None
        targets = [canonical_gene] if canonical_gene else peak_to_genes.get(row.get("peak_id", ""), [])
        if targets:
            for index, target in enumerate(targets, 1):
                rows.append(_base_row("chipseq", "differential_binding", row, reference_id, target, "gene", contrasts, marks, f".gene{index}" if len(targets) > 1 else ""))
        else:
            peak_id = row.get("peak_id", "")
            if not peak_id:
                raise ValueError(f"differential binding evidence {row['evidence_id']} has neither gene nor peak identity")
            rows.append(_base_row("chipseq", "differential_binding", row, reference_id, f"region:{reference_id}:{peak_id}", "region", contrasts, marks))
    observation_ids = [row["observation_id"] for row in rows]
    if len(observation_ids) != len(set(observation_ids)):
        raise ValueError("duplicate integrated observation_id")
    return sorted(rows, key=lambda row: (row["canonical_entity_id"], row["source_assay"], row["evidence_type"], row["observation_id"]))


def _peak_aggregation(long_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in long_rows:
        if row["entity_type"] == "gene" and row["evidence_type"] == "peak_gene":
            grouped[(row["canonical_entity_id"], row["canonical_mark"], row["canonical_context"])].append(row)
    result = []
    for (entity, mark, context), items in sorted(grouped.items()):
        relationships = [item["peak_relationship"].casefold() for item in items]
        promoter = sum("promoter" in value for value in relationships)
        body = sum(value in {"gene", "exon", "intron", "gene_body"} for value in relationships)
        result.append({"canonical_entity_id": entity, "canonical_mark": mark, "canonical_context": context, "total_associated_peaks": str(len(items)), "promoter_peaks": str(promoter), "gene_body_peaks": str(body), "distal_peaks": str(len(items) - promoter - body), "peak_ids": ";".join(sorted({item["peak_id"] for item in items})), "source_evidence_ids": ";".join(sorted({item["source_evidence_id"] for item in items}))})
    return result


def _master_rows(entity_rows: list[dict[str, str]], long_rows: list[dict[str, str]], chip_has_peak_gene: bool, reference_id: str) -> list[dict[str, str]]:
    genes = sorted({row["canonical_entity_id"] for row in entity_rows})
    by_gene: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in long_rows:
        if row["entity_type"] == "gene":
            by_gene[row["canonical_entity_id"]].append(row)
    output = []
    for gene in genes:
        items = by_gene.get(gene, [])
        rna = [row for row in items if row["source_assay"] == "rnaseq"]
        chip = [row for row in items if row["source_assay"] == "chipseq"]
        chip_state = "MEASURED" if chip else "NO_PEAK" if chip_has_peak_gene else "NOT_MEASURED"
        output.append({
            "canonical_entity_id": gene, "reference_id": reference_id, "rna_evidence_state": "MEASURED" if rna else "NOT_MEASURED",
            "chip_evidence_state": chip_state, "expression_observations": str(sum(row["evidence_type"] == "expression" for row in items)),
            "differential_expression_observations": str(sum(row["evidence_type"] == "differential_expression" for row in items)),
            "peak_associations": str(sum(row["evidence_type"] == "peak_gene" for row in items)),
            "differential_binding_observations": str(sum(row["evidence_type"] == "differential_binding" for row in items)),
            "marks_or_factors": ";".join(sorted({row["canonical_mark"] for row in chip if row["canonical_mark"]})),
            "contexts": ";".join(sorted({row["canonical_context"] for row in items if row["canonical_context"]})),
            "canonical_contrasts": ";".join(sorted({row["canonical_contrast_id"] for row in items if row["canonical_contrast_id"]})),
            "rna_evidence_ids": ";".join(sorted({row["source_evidence_id"] for row in rna})),
            "chip_evidence_ids": ";".join(sorted({row["source_evidence_id"] for row in chip})),
        })
    return output


def build_master_evidence(rna_dir: Path, chip_dir: Path, harmonization_dir: Path, output: Path) -> dict[str, Any]:
    rna_manifest, rna_data = load_evidence_bundle(rna_dir)
    chip_manifest, chip_data = load_evidence_bundle(chip_dir)
    errors = reference_errors(rna_manifest, chip_manifest)
    if errors:
        raise ValueError("reference incompatibility: " + "; ".join(errors))
    harmonization_manifest = read_json(harmonization_dir / "harmonization_manifest.json")
    if harmonization_manifest.get("reference", {}).get("reference_id") != rna_manifest["reference_id"]:
        raise ValueError("harmonization reference does not match evidence bundles")
    entity_rows, entities, contrasts, marks = _lookups(harmonization_dir)
    reference_id = rna_manifest["reference_id"]
    long_rows = _build_long(rna_data, chip_data, reference_id, entities, contrasts, marks)
    peak_rows = _peak_aggregation(long_rows)
    master_rows = _master_rows(entity_rows, long_rows, "peak_gene" in chip_data, reference_id)
    output.mkdir(parents=True, exist_ok=True)
    write_tsv(output / "master_evidence_long.tsv", LONG_FIELDS, long_rows)
    write_tsv(output / "master_evidence.tsv", MASTER_FIELDS, master_rows)
    write_tsv(output / "peak_aggregation.tsv", PEAK_AGG_FIELDS, peak_rows)
    datasets = []
    for kind, filename, count in (("master_evidence_long", "master_evidence_long.tsv", len(long_rows)), ("master_evidence", "master_evidence.tsv", len(master_rows)), ("peak_aggregation", "peak_aggregation.tsv", len(peak_rows))):
        datasets.append({"dataset_type": kind, "path": filename, "records": count, "checksum": {"algorithm": "sha256", "value": sha256(output / filename)}})
    document = {"schema_version": "1.0", "integration_model_version": "1.0", "type": "molecular_evidence_integration", "id": f"{rna_manifest['id']}--{chip_manifest['id']}.integration", "status": "complete", "reference": rna_manifest["reference"], "input_evidence_manifests": [{"id": rna_manifest["id"], "assay": "rnaseq", "checksum": {"algorithm": "sha256", "value": sha256(Path(rna_dir) / "evidence_manifest.json")}}, {"id": chip_manifest["id"], "assay": "chipseq", "checksum": {"algorithm": "sha256", "value": sha256(Path(chip_dir) / "evidence_manifest.json")}}], "harmonization_manifest_id": harmonization_manifest["id"], "harmonization_manifest_checksum": {"algorithm": "sha256", "value": sha256(harmonization_dir / "harmonization_manifest.json")}, "datasets": datasets, "record_counts": {"canonical_genes": len(master_rows), "long_observations": len(long_rows), "peak_groups": len(peak_rows)}, "provenance": {"provider": "molecular_evidence_integration", "provider_version": "1.0"}}
    (output / "integration_manifest.json").write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    from integration.validation import validate_integration
    errors = validate_integration(document, output)
    if errors:
        raise ValueError("invalid molecular integration output: " + "; ".join(errors))
    return document
