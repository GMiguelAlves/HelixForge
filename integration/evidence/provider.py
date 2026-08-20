from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .io import first_column, optional_number, read_json, read_tsv, safe_id, sha256, write_tsv
from .validation import validate_evidence_manifest


RNA_TYPES = {"gene_abundance", "gene_counts", "normalized_counts", "differential_expression", "differential_expression_summary"}
CHIP_TYPES = {"peak_set", "consensus_peaks", "idr_peaks", "peak_gene_annotation", "differential_binding"}

EXPRESSION_FIELDS = ["evidence_id", "source_entity_id", "normalized_entity_id", "normalization_rule", "sample_id", "condition", "stage", "measurement", "unit", "source_artifact_id"]
DE_FIELDS = ["evidence_id", "source_entity_id", "normalized_entity_id", "normalization_rule", "contrast_id", "numerator", "denominator", "base_mean", "log2_fold_change", "pvalue", "padj", "statistic", "standard_error", "statistical_method", "source_artifact_id"]
PEAK_FIELDS = ["evidence_id", "peak_id", "mark_or_factor", "condition", "stage", "sample_ids", "chromosome", "start", "end", "peak_type", "score", "strand", "signal_value", "pvalue_score", "qvalue_score", "summit", "source_artifact_id"]
PEAK_GENE_FIELDS = ["evidence_id", "peak_id", "source_entity_id", "normalized_entity_id", "normalization_rule", "relationship", "distance_to_tss", "position_class", "mark_or_factor", "condition", "stage", "source_artifact_id"]
CONSENSUS_FIELDS = ["evidence_id", "peak_id", "mark_or_factor", "condition", "stage", "chromosome", "start", "end", "peak_type", "support", "support_replicates", "strategy", "source_artifact_id"]
DB_FIELDS = ["evidence_id", "peak_id", "source_entity_id", "normalized_entity_id", "normalization_rule", "contrast_id", "numerator", "denominator", "mark_or_factor", "base_mean", "log2_fold_change", "pvalue", "padj", "statistic", "standard_error", "statistical_method", "source_artifact_id"]


def _sample_context(manifest: dict[str, Any]) -> dict[str, dict[str, str]]:
    return {sample.get("sample_id", sample.get("record_id")): sample for sample in manifest.get("samples", [])}


def _contrast(manifest: dict[str, Any], contrast_id: str) -> dict[str, Any]:
    matches = {item["contrast_id"]: item for item in manifest.get("contrasts", [])}
    if contrast_id not in matches:
        raise ValueError(f"unknown contrast_id {contrast_id!r}")
    return matches[contrast_id]


def _dataset(output: Path, evidence_type: str, filename: str, schema: str, entity_type: str, rows: list[dict[str, Any]], fields: list[str], unit: str | None = None) -> dict[str, Any] | None:
    if not rows:
        return None
    target = output / filename
    count = write_tsv(target, fields, rows)
    return {"dataset_id": f"evidence.{evidence_type}", "evidence_type": evidence_type, "entity_type": entity_type, "format": "tsv", "path": filename, "schema": schema, "unit": unit, "records": count, "checksum": {"algorithm": "sha256", "value": sha256(target)}}


def _rna(manifest: dict[str, Any], bindings: dict[str, Path], output: Path) -> list[dict[str, Any]]:
    expression, differential = [], []
    samples = _sample_context(manifest)
    unit_by_type = {"gene_abundance": "TPM", "gene_counts": "counts", "normalized_counts": "normalized_counts"}
    de_artifacts = [item for item in manifest.get("artifacts", []) if item.get("artifact_type") in {"differential_expression", "differential_expression_summary"}]
    prefer_contrast_de = any(item.get("artifact_type") == "differential_expression" and item.get("contrast_id") for item in de_artifacts)
    for artifact in manifest.get("artifacts", []):
        kind, artifact_id = artifact["artifact_type"], artifact["artifact_id"]
        if kind not in RNA_TYPES:
            continue
        if prefer_contrast_de and kind == "differential_expression_summary":
            continue
        if artifact_id not in bindings:
            raise ValueError(f"missing explicit binding for integration evidence artifact {artifact_id}")
        fields, rows = read_tsv(bindings[artifact_id])
        gene_col = first_column(fields, ["gene_id", "gene", "id", "feature_id"])
        if not gene_col:
            raise ValueError(f"{artifact_id}: gene identifier column is missing")
        if kind not in {"differential_expression", "differential_expression_summary"}:
            for row_index, row in enumerate(rows, 1):
                gene = row.get(gene_col, "").strip()
                if not gene:
                    raise ValueError(f"{artifact_id}: missing gene_id at row {row_index}")
                for sample_id in [field for field in fields if field != gene_col]:
                    value = optional_number(row.get(sample_id))
                    if not value:
                        continue
                    context = samples.get(sample_id, {})
                    expression.append({"evidence_id": f"rna.expression.{safe_id(artifact_id)}.{row_index}.{safe_id(sample_id)}", "source_entity_id": gene, "normalized_entity_id": "", "normalization_rule": "none", "sample_id": sample_id, "condition": context.get("condition", ""), "stage": context.get("stage", ""), "measurement": value, "unit": unit_by_type[kind], "source_artifact_id": artifact_id})
            continue
        contrast_col = first_column(fields, ["contrast_id", "contrast", "comparison"])
        lfc_col = first_column(fields, ["log2FoldChange", "log2FC", "logFC", "lfc"])
        if not lfc_col:
            raise ValueError(f"{artifact_id}: differential expression effect column is missing")
        for row_index, row in enumerate(rows, 1):
            gene = row.get(gene_col, "").strip()
            contrast_id = (row.get(contrast_col, "") if contrast_col else artifact.get("contrast_id")) or ""
            contrast = _contrast(manifest, contrast_id)
            differential.append({"evidence_id": f"rna.de.{safe_id(artifact_id)}.{row_index}", "source_entity_id": gene, "normalized_entity_id": "", "normalization_rule": "none", "contrast_id": contrast_id, "numerator": contrast.get("numerator", ""), "denominator": contrast.get("denominator", ""), "base_mean": optional_number(row.get(first_column(fields, ["baseMean", "base_mean"]) or "")), "log2_fold_change": optional_number(row.get(lfc_col)), "pvalue": optional_number(row.get(first_column(fields, ["pvalue", "P.Value", "p_value"]) or "")), "padj": optional_number(row.get(first_column(fields, ["padj", "FDR", "qvalue", "adj.P.Val"]) or "")), "statistic": optional_number(row.get(first_column(fields, ["statistic", "stat", "WaldStatistic"]) or "")), "standard_error": optional_number(row.get(first_column(fields, ["lfcSE", "standard_error"]) or "")), "statistical_method": artifact.get("source", {}).get("name") or "", "source_artifact_id": artifact_id})
    datasets = [
        _dataset(output, "expression", "expression.tsv", "expression-record.schema.json", "gene", expression, EXPRESSION_FIELDS, "mixed_explicit"),
        _dataset(output, "differential_expression", "differential_expression.tsv", "differential-expression-record.schema.json", "gene", differential, DE_FIELDS),
    ]
    return [item for item in datasets if item]


def _bed_rows(path: Path, artifact: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for row_index, line in enumerate(handle, 1):
            if not line.strip() or line.startswith(('#', 'track', 'browser')):
                continue
            values = line.rstrip("\n\r").split("\t")
            if len(values) < 3:
                raise ValueError(f"{artifact['artifact_id']}: invalid BED row {row_index}")
            rows.append({"values": values, "row_index": row_index})
    return rows


def _chip(manifest: dict[str, Any], bindings: dict[str, Path], output: Path) -> list[dict[str, Any]]:
    peaks, associations, consensus, differential = [], [], [], []
    peak_ids: set[str] = set()
    bound_db = [item for item in manifest.get("artifacts", []) if item.get("artifact_type") == "differential_binding" and item.get("artifact_id") in bindings]
    prefer_contrast_db = any(item.get("contrast_id") for item in bound_db)
    artifact_by_id = {item["artifact_id"]: item for item in manifest.get("artifacts", [])}
    for artifact in manifest.get("artifacts", []):
        kind, artifact_id = artifact["artifact_type"], artifact["artifact_id"]
        if kind not in CHIP_TYPES:
            continue
        if kind == "differential_binding" and prefer_contrast_db and not artifact.get("contrast_id"):
            continue
        if artifact_id not in bindings:
            raise ValueError(f"missing explicit binding for integration evidence artifact {artifact_id}")
        path = bindings[artifact_id]
        mark = artifact.get("mark_or_factor") or ";".join(artifact.get("marks_or_factors", []))
        common = {"mark_or_factor": mark, "condition": artifact.get("condition") or "", "stage": artifact.get("stage") or "", "source_artifact_id": artifact_id}
        if kind == "peak_set":
            for item in _bed_rows(path, artifact):
                values, idx = item["values"], item["row_index"]
                peak_id = values[3] if len(values) > 3 and values[3] else f"{artifact_id}.{idx}"
                peak_ids.add(peak_id)
                peaks.append({"evidence_id": f"chip.peak.{safe_id(artifact_id)}.{idx}", "peak_id": peak_id, **common, "sample_ids": ";".join(artifact.get("sample_ids", [])), "chromosome": values[0], "start": values[1], "end": values[2], "peak_type": artifact.get("peak_type") or "", "score": values[4] if len(values) > 4 else "", "strand": values[5] if len(values) > 5 else "", "signal_value": values[6] if len(values) > 6 else "", "pvalue_score": values[7] if len(values) > 7 else "", "qvalue_score": values[8] if len(values) > 8 else "", "summit": values[9] if len(values) > 9 else ""})
        elif kind in {"consensus_peaks", "idr_peaks"}:
            if artifact.get("format", "").lower() == "bed":
                parsed = _bed_rows(path, artifact)
                for item in parsed:
                    values, idx = item["values"], item["row_index"]
                    peak_id = values[3] if len(values) > 3 and values[3] else f"{artifact_id}.{idx}"
                    peak_ids.add(peak_id)
                    consensus.append({"evidence_id": f"chip.consensus.{safe_id(artifact_id)}.{idx}", "peak_id": peak_id, **common, "chromosome": values[0], "start": values[1], "end": values[2], "peak_type": artifact.get("peak_type") or "", "support": "", "support_replicates": "", "strategy": artifact.get("metadata", {}).get("strategy", "idr" if kind == "idr_peaks" else "")})
            else:
                fields, rows = read_tsv(path)
                for idx, row in enumerate(rows, 1):
                    peak_id = row.get(first_column(fields, ["peak_id", "id", "name"]) or "", "") or f"{artifact_id}.{idx}"
                    peak_ids.add(peak_id)
                    consensus.append({"evidence_id": f"chip.consensus.{safe_id(artifact_id)}.{idx}", "peak_id": peak_id, **common, "chromosome": row.get(first_column(fields, ["chrom", "chromosome"]) or "", ""), "start": row.get("start", ""), "end": row.get("end", ""), "peak_type": artifact.get("peak_type") or "", "support": row.get("support", ""), "support_replicates": row.get("support_replicates", ""), "strategy": artifact.get("metadata", {}).get("strategy", "idr" if kind == "idr_peaks" else "")})
        elif kind == "peak_gene_annotation":
            fields, rows = read_tsv(path)
            for idx, row in enumerate(rows, 1):
                peak_id = row.get(first_column(fields, ["peak_id", "id"]) or "", "")
                gene = row.get(first_column(fields, ["gene_id", "associated_gene_id", "nearest_gene_id"]) or "", "")
                source_peak = artifact_by_id.get(row.get("source_id", ""), {})
                row_common = dict(common)
                row_common["mark_or_factor"] = row.get(first_column(fields, ["mark_or_factor", "mark", "factor"]) or "", "") or source_peak.get("mark_or_factor") or mark
                row_common["condition"] = row.get(first_column(fields, ["condition", "stage_or_condition"]) or "", "") or source_peak.get("condition") or common["condition"]
                row_common["stage"] = row.get("stage", "") or source_peak.get("stage") or common["stage"]
                associations.append({"evidence_id": f"chip.peak_gene.{safe_id(artifact_id)}.{idx}", "peak_id": peak_id, "source_entity_id": gene, "normalized_entity_id": "", "normalization_rule": "none", "relationship": row.get(first_column(fields, ["relationship", "category", "genomic_annotation"]) or "", ""), "distance_to_tss": optional_number(row.get(first_column(fields, ["distance_to_tss", "distance"]) or "")), "position_class": row.get(first_column(fields, ["position_class", "category", "genomic_annotation"]) or "", ""), **row_common})
        elif kind == "differential_binding":
            fields, rows = read_tsv(path)
            for idx, row in enumerate(rows, 1):
                contrast_id = row.get(first_column(fields, ["contrast_id", "contrast", "comparison"]) or "", "") or artifact.get("contrast_id") or ""
                contrast = _contrast(manifest, contrast_id)
                row_mark = row.get(first_column(fields, ["mark_or_factor", "mark", "factor"]) or "", "") or mark
                differential.append({"evidence_id": f"chip.db.{safe_id(artifact_id)}.{idx}", "peak_id": row.get(first_column(fields, ["peak_id", "id", "region"]) or "", ""), "source_entity_id": row.get(first_column(fields, ["gene_id", "associated_gene_id", "nearest_gene_id"]) or "", ""), "normalized_entity_id": "", "normalization_rule": "none", "contrast_id": contrast_id, "numerator": contrast.get("numerator", ""), "denominator": contrast.get("denominator", ""), "mark_or_factor": row_mark, "base_mean": optional_number(row.get(first_column(fields, ["baseMean", "base_mean"]) or "")), "log2_fold_change": optional_number(row.get(first_column(fields, ["log2FoldChange", "log2FC", "logFC"]) or "")), "pvalue": optional_number(row.get(first_column(fields, ["pvalue", "P.Value", "p_value"]) or "")), "padj": optional_number(row.get(first_column(fields, ["padj", "FDR", "qvalue", "adj.P.Val"]) or "")), "statistic": optional_number(row.get(first_column(fields, ["statistic", "stat"]) or "")), "standard_error": optional_number(row.get(first_column(fields, ["lfcSE", "standard_error"]) or "")), "statistical_method": artifact.get("source", {}).get("name") or "", "source_artifact_id": artifact_id})
    datasets = [
        _dataset(output, "peak", "peaks.tsv", "peak-record.schema.json", "peak", peaks, PEAK_FIELDS),
        _dataset(output, "peak_gene", "peak_gene.tsv", "peak-gene-record.schema.json", "peak_gene", associations, PEAK_GENE_FIELDS),
        _dataset(output, "consensus", "consensus.tsv", "consensus-record.schema.json", "peak", consensus, CONSENSUS_FIELDS),
        _dataset(output, "differential_binding", "differential_binding.tsv", "differential-binding-record.schema.json", "peak", differential, DB_FIELDS),
    ]
    return [item for item in datasets if item]


def _classification(artifact_type: str) -> str:
    if artifact_type in RNA_TYPES | CHIP_TYPES:
        return "INTEGRATION_EVIDENCE"
    if artifact_type in {"aligned_bam", "peak_qc"}:
        return "SUPPORTING_ARTIFACT"
    if artifact_type == "signal_track":
        return "VISUALIZATION_ARTIFACT"
    return "PROVENANCE_ONLY"


def build_evidence(manifest: dict[str, Any], bindings: dict[str, Path], output: Path) -> dict[str, Any]:
    assay = "rnaseq" if manifest.get("type") == "rnaseq_run_manifest" else "chipseq" if manifest.get("type") == "chipseq_run_manifest" else ""
    if not assay:
        raise ValueError("unsupported terminal run manifest type")
    output.mkdir(parents=True, exist_ok=True)
    catalog = []
    manifest_artifact_ids = {item["artifact_id"] for item in manifest.get("artifacts", [])}
    unknown_bindings = set(bindings) - manifest_artifact_ids
    if unknown_bindings:
        raise ValueError(f"bindings reference unknown artifacts: {sorted(unknown_bindings)}")
    for artifact in manifest.get("artifacts", []):
        if artifact.get("reference_id") != manifest["reference"]["reference_id"]:
            raise ValueError(f"artifact {artifact['artifact_id']} has inconsistent reference_id")
        if artifact["artifact_id"] in bindings and artifact.get("checksum"):
            checksum = artifact["checksum"]
            if checksum.get("algorithm") != "sha256" or sha256(bindings[artifact["artifact_id"]]) != checksum.get("value"):
                raise ValueError(f"artifact {artifact['artifact_id']} checksum mismatch")
        catalog.append({"artifact_id": artifact["artifact_id"], "artifact_type": artifact["artifact_type"], "classification": _classification(artifact["artifact_type"]), "reference_id": artifact["reference_id"], "source": artifact["source"], "provenance": artifact["provenance"], "bound": artifact["artifact_id"] in bindings})
    datasets = _rna(manifest, bindings, output) if assay == "rnaseq" else _chip(manifest, bindings, output)
    document = {"schema_version": "1.0", "evidence_model_version": "1.1", "type": "evidence_manifest", "id": f"{manifest['id']}.evidence", "assay": assay, "run_id": manifest["run"]["run_id"], "reference_id": manifest["reference"]["reference_id"], "reference": manifest["reference"], "source_run_manifest_id": manifest["id"], "status": "complete" if datasets else "complete_empty", "contrasts": manifest.get("contrasts", []), "datasets": datasets, "artifact_catalog": catalog, "provenance": {"provider": f"{assay}_evidence_provider", "provider_version": "1.1", "source_run_manifest_id": manifest["id"]}}
    errors = validate_evidence_manifest(document, output)
    if errors:
        raise ValueError("invalid evidence: " + "; ".join(errors))
    (output / "evidence_manifest.json").write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return document
