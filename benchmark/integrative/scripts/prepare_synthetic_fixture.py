#!/usr/bin/env python3
"""Create positive 10B inputs without importing HelixForge implementation code."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


SCIENTIFIC_TARGET = "dc0218ce902302da476910595bb133c82fee927c"
TRUTH_COMMIT = "1b7e2fa"


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return list(reader.fieldnames or []), list(reader)


def write_tsv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def dump_json(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def provenance(process: str) -> dict[str, Any]:
    return {
        "producer_workflow": "integrative_synthetic_fixture",
        "producer_process": process,
        "software": [{"name": "python", "version": "stdlib", "container": None}],
        "parameters": {"scientific_target": SCIENTIFIC_TARGET},
        "source_manifest_ids": ["helixforge_integrative_synthetic_v1"],
        "source_artifact_ids": [],
        "execution_metadata": None,
    }


def reference() -> dict[str, Any]:
    return {
        "reference_id": "synthetic_integrative_v1",
        "display_name": "HelixForge integrative synthetic reference v1",
        "organism": "synthetic_organism",
        "species": "synthetic_organism",
        "assembly": "synthetic_integrative_assembly_v1",
        "genome_id": "synthetic_integrative_genome_v1",
        "annotation_id": "synthetic_integrative_annotation_v1",
        "resources": {},
        "source": {"type": "external", "name": "frozen synthetic design", "version": "1.0"},
        "metadata": {"coordinate_system": "synthetic", "truth_commit": TRUTH_COMMIT},
    }


def artifact(identifier: str, kind: str, assay: str, filename: str, checksum: str, **context: Any) -> dict[str, Any]:
    value = {
        "artifact_id": identifier,
        "artifact_type": kind,
        "assay": assay,
        "format": context.pop("format", "tsv"),
        "entity_level": context.pop("entity_level", "gene"),
        "reference_id": "synthetic_integrative_v1",
        "contrast_id": context.pop("contrast_id", None),
        "sample_ids": context.pop("sample_ids", []),
        "condition": context.pop("condition", None),
        "stage": context.pop("stage", None),
        "mark_or_factor": context.pop("mark_or_factor", None),
        "marks_or_factors": context.pop("marks_or_factors", []),
        "peak_type": context.pop("peak_type", None),
        "role": context.pop("role", "synthetic_positive_fixture"),
        "location": {"kind": "manifest_relative", "path": f"integration_artifacts/{filename}", "base_path": None},
        "checksum": {"algorithm": "sha256", "value": checksum},
        "source": {"type": "external", "name": "independent synthetic fixture generator", "version": "1.0"},
        "provenance": provenance("PREPARE_SYNTHETIC_FIXTURE"),
        "metadata": context,
    }
    return value


def source_gene(row: dict[str, str], assay: str) -> str:
    value = row[f"source_{assay}_gene_id"]
    return value if value != "NOT_APPLICABLE" else ""


def numeric(value: str, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def build_rna(rows: list[dict[str, str]], root: Path) -> tuple[Path, list[dict[str, Any]]]:
    directory = root / "rna"
    artifacts = directory / "integration_artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    main_expression: list[dict[str, Any]] = []
    adult_expression: list[dict[str, Any]] = []
    differential: list[dict[str, Any]] = []
    for index, row in enumerate(rows, 1):
        if row["rna_evidence_state"] == "NOT_MEASURED":
            continue
        gene = source_gene(row, "rna")
        lfc = numeric(row["rna_log2fc"])
        base = 40.0 + (index % 31)
        if row["rna_observation_state"] == "MISSING":
            values = {"adult_1": "", "adult_2": ""} if row["source_context"] == "adults" else {
                "control_1": "", "control_2": "", "treated_1": "", "treated_2": ""
            }
        elif row["source_context"] == "adults":
            values = {"adult_1": f"{base:.6f}", "adult_2": f"{base * 1.03:.6f}"}
        else:
            treated = base * math.pow(2.0, lfc)
            values = {
                "control_1": f"{base:.6f}", "control_2": f"{base * 1.02:.6f}",
                "treated_1": f"{treated:.6f}", "treated_2": f"{treated * 0.98:.6f}",
            }
        target = adult_expression if row["source_context"] == "adults" else main_expression
        target.append({"gene_id": gene, **values})
        missing = row["rna_observation_state"] == "MISSING"
        differential.append({
            "gene_id": gene,
            "contrast_id": "treated_vs_control",
            "baseMean": f"{base:.6f}",
            "log2FoldChange": "" if missing else row["rna_log2fc"],
            "lfcSE": "" if missing else "0.2",
            "statistic": "" if missing else f"{lfc / 0.2:.6f}",
            "pvalue": "" if missing else row["rna_padj"],
            "padj": "" if missing else row["rna_padj"],
        })

    main_path = artifacts / "rna_abundance_main.tsv"
    adult_path = artifacts / "rna_abundance_adult.tsv"
    de_path = artifacts / "rna_differential_expression.tsv"
    write_tsv(main_path, ["gene_id", "control_1", "control_2", "treated_1", "treated_2"], main_expression)
    write_tsv(adult_path, ["gene_id", "adult_1", "adult_2"], adult_expression)
    write_tsv(de_path, ["gene_id", "contrast_id", "baseMean", "log2FoldChange", "lfcSE", "statistic", "pvalue", "padj"], differential)

    samples = []
    for sample_id, condition, stage, replicate in (
        ("control_1", "control", None, 1), ("control_2", "control", None, 2),
        ("treated_1", "treated", None, 1), ("treated_2", "treated", None, 2),
        ("adult_1", "adult", "adults", 1), ("adult_2", "adult", "adults", 2),
    ):
        samples.append({"sample_id": sample_id, "dataset": "synthetic_integrative_v1", "condition": condition, "stage": stage, "batch": None, "biological_replicate": replicate, "technical_runs": [sample_id]})
    contrast = {"contrast_id": "treated_vs_control", "factor": "condition", "numerator": "treated", "denominator": "control", "label": "treated vs control", "formula": "~ condition", "covariates": [], "assay": ["rnaseq"], "metadata": {}}
    declared = [
        artifact("rna.abundance.main", "gene_abundance", "rnaseq", main_path.name, sha256(main_path), sample_ids=["control_1", "control_2", "treated_1", "treated_2"]),
        artifact("rna.abundance.adult", "gene_abundance", "rnaseq", adult_path.name, sha256(adult_path), sample_ids=["adult_1", "adult_2"]),
        artifact("rna.de", "differential_expression", "rnaseq", de_path.name, sha256(de_path), contrast_id="treated_vs_control", role="contrast_results"),
    ]
    manifest = {
        "schema_version": "1.0", "integration_api_version": "1.0", "type": "rnaseq_run_manifest",
        "id": "integrative.synthetic.rnaseq", "status": "complete",
        "run": {"workflow": "rnaseq", "run_id": "integrative-synthetic-rna", "run_name": "integrative synthetic RNA evidence", "created_at": None, "helixforge_version": "1.0.0-rc.1", "git_commit": SCIENTIFIC_TARGET, "nextflow_version": "not_applicable_external_fixture", "profile": "synthetic", "source": {"type": "external", "name": "independent synthetic fixture generator", "version": "1.0"}},
        "reference": reference(), "samples": samples, "conditions": ["control", "treated", "adult"], "stages": ["adults"], "batches": [], "quantification_method": "synthetic_evidence", "contrasts": [contrast], "artifacts": declared, "provenance": provenance("PREPARE_SYNTHETIC_RNA"),
    }
    manifest_path = directory / "rnaseq_run_manifest.json"
    dump_json(manifest_path, manifest)
    return manifest_path, declared


def relationships(row: dict[str, str], count: int) -> list[str]:
    values = row["peak_relationships"].split(";") if row["peak_relationships"] != "NOT_APPLICABLE" else []
    if not values:
        return []
    return [values[index % len(values)] for index in range(count)]


def build_chip(rows: list[dict[str, str]], root: Path) -> tuple[Path, list[dict[str, Any]]]:
    directory = root / "chip"
    artifacts_dir = directory / "integration_artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    beds: dict[tuple[str, str], list[str]] = defaultdict(list)
    annotations: list[dict[str, Any]] = []
    differential: list[dict[str, Any]] = []
    peak_counter = 0
    for index, row in enumerate(rows, 1):
        if row["chip_evidence_state"] != "MEASURED":
            continue
        gene = source_gene(row, "chip")
        mark = row["source_mark"]
        primary_count = max(1, int(row["peak_count"] or 1))
        rels = relationships(row, primary_count)
        contexts = [row["source_context"]]
        if row["source_context"] != "adults":
            contexts = ["control", "treated"]
        primary_peak_id = ""
        for context in contexts:
            context_count = primary_count
            if row["chip_direction"] == "INCREASED" and context == "control":
                context_count = max(1, primary_count - 1)
            elif row["chip_direction"] == "DECREASED" and context == "treated":
                context_count = max(1, primary_count - 1)
            for offset in range(context_count):
                peak_counter += 1
                shared = row["multi_gene_region_id"] if offset == 0 and row["multi_gene_region_id"] else ""
                peak_id = shared or f"SYN_PEAK_{peak_counter:06d}"
                if not primary_peak_id and context == row["source_context"]:
                    primary_peak_id = peak_id
                start = 1000 + peak_counter * 100
                beds[(mark, context)].append(f"chrS\t{start}\t{start + 80}\t{peak_id}\t100\t.\t10\t8\t7\t40")
                relationship = rels[offset % len(rels)] if rels else "distal"
                annotations.append({
                    "peak_id": peak_id, "gene_id": gene, "relationship": relationship,
                    "distance_to_tss": "0" if "promoter" in relationship else "500" if relationship == "proximal" else "5000",
                    "position_class": relationship, "mark_or_factor": mark, "condition": context,
                    "stage": "adults" if context == "adults" else "", "source_id": f"chip.peaks.{safe_token(mark)}.{safe_token(context)}",
                })
        if row["multi_gene_region_id"]:
            # Evidence Model 1.1 keys differential-binding observations by
            # region/contrast/artifact, independently of the associated gene.
            # Keep the shared region exclusively in peak→gene evidence and use
            # a deterministic, known carrier region for each gene-level DB row.
            peak_counter += 1
            primary_peak_id = f"SYN_DB_PEAK_{index:06d}"
            start = 1000 + peak_counter * 100
            carrier_context = row["source_context"]
            beds[(mark, carrier_context)].append(f"chrS\t{start}\t{start + 80}\t{primary_peak_id}\t100\t.\t10\t8\t7\t40")
        if not primary_peak_id:
            primary_peak_id = annotations[-1]["peak_id"]
        missing = row["chip_observation_state"] == "MISSING"
        differential.append({
            "peak_id": primary_peak_id, "gene_id": gene, "contrast_id": "treatment_effect", "mark_or_factor": mark,
            "baseMean": "50", "log2FoldChange": "" if missing else row["chip_log2fc"], "lfcSE": "" if missing else "0.2",
            "statistic": "" if missing else f"{numeric(row['chip_log2fc']) / 0.2:.6f}",
            "pvalue": "" if missing else row["chip_padj"], "padj": "" if missing else row["chip_padj"],
        })

    declared: list[dict[str, Any]] = []
    all_marks = sorted({row["source_mark"] for row in rows if row["source_mark"] != "NOT_APPLICABLE"})
    sample_records = []
    for (mark, context), bed_rows in sorted(beds.items()):
        identifier = f"chip.peaks.{safe_token(mark)}.{safe_token(context)}"
        mark_token = hashlib.sha256(mark.encode("utf-8")).hexdigest()[:8]
        filename = f"{safe_token(mark)}.{mark_token}.{safe_token(context)}.narrowPeak"
        path = artifacts_dir / filename
        path.write_text("\n".join(bed_rows) + "\n", encoding="utf-8")
        sample_id = f"{safe_token(mark)}_{safe_token(context)}"
        declared.append(artifact(identifier, "peak_set", "chipseq", filename, sha256(path), format="narrowPeak", entity_level="peak", sample_ids=[sample_id], condition=context if context != "adults" else "adult", stage="adults" if context == "adults" else None, mark_or_factor=mark, peak_type="narrow"))
        sample_records.append({"record_id": sample_id, "sample_id": sample_id, "dataset": "synthetic_integrative_v1", "condition": context if context != "adults" else "adult", "stage": "adults" if context == "adults" else None, "biological_replicate": 1, "technical_replicate": 1, "is_control": False, "control_record_id": None, "mark_or_factor": mark, "antibody": None})

    annotation_path = artifacts_dir / "peak_gene_annotation.tsv"
    write_tsv(annotation_path, ["peak_id", "gene_id", "relationship", "distance_to_tss", "position_class", "mark_or_factor", "condition", "stage", "source_id"], annotations)
    db_path = artifacts_dir / "differential_binding.tsv"
    write_tsv(db_path, ["peak_id", "gene_id", "contrast_id", "mark_or_factor", "baseMean", "log2FoldChange", "lfcSE", "statistic", "pvalue", "padj"], differential)
    declared.extend([
        artifact("chip.annotation", "peak_gene_annotation", "chipseq", annotation_path.name, sha256(annotation_path), entity_level="peak", marks_or_factors=all_marks),
        artifact("chip.db", "differential_binding", "chipseq", db_path.name, sha256(db_path), entity_level="peak", contrast_id="treatment_effect", marks_or_factors=all_marks, role="contrast_results"),
    ])
    contrast = {"contrast_id": "treatment_effect", "factor": "condition", "numerator": "treated", "denominator": "control", "label": "treated vs control", "formula": "~ condition", "covariates": [], "assay": ["chipseq"], "metadata": {}}
    manifest = {
        "schema_version": "1.0", "integration_api_version": "1.0", "type": "chipseq_run_manifest",
        "id": "integrative.synthetic.chipseq", "status": "complete",
        "run": {"workflow": "chipseq", "run_id": "integrative-synthetic-chip", "run_name": "integrative synthetic ChIP evidence", "created_at": None, "helixforge_version": "1.0.0-rc.1", "git_commit": SCIENTIFIC_TARGET, "nextflow_version": "not_applicable_external_fixture", "profile": "synthetic", "source": {"type": "external", "name": "independent synthetic fixture generator", "version": "1.0"}},
        "reference": reference(), "samples": sample_records, "conditions": ["control", "treated", "adult"], "marks_or_factors": all_marks, "contrasts": [contrast], "artifacts": declared, "provenance": provenance("PREPARE_SYNTHETIC_CHIP"),
    }
    manifest_path = directory / "chipseq_run_manifest.json"
    dump_json(manifest_path, manifest)
    return manifest_path, declared


def safe_token(value: str) -> str:
    return "".join(char if char.isalnum() or char in "._-" else "_" for char in value).strip("_")


def build_policies(rows: list[dict[str, str]], root: Path) -> None:
    aliases = {
        row["source_rna_gene_id"]: row["gene_id"]
        for row in rows
        if row["normalization_case"] == "explicit_alias_map" and row["source_rna_gene_id"] != "NOT_APPLICABLE"
    }
    dump_json(root / "harmonization_policy.json", {"schema_version": "1.0", "entity_aliases": aliases, "strip_version_suffix": True})
    context_fields = ["canonical_entity_id", "gene_name", "is_gene_of_interest", "is_epigenetic_machinery", "machinery_group", "wgcna_hit", "mfuzz_hit", "dtu_hit", "splicing_hit", "functional_annotation"]
    context_rows = []
    for row in rows:
        if row["candidate_context_flags"] == "none":
            continue
        context_rows.append({"canonical_entity_id": row["gene_id"], "gene_name": row["gene_id"], "is_gene_of_interest": "true", "is_epigenetic_machinery": "false", "machinery_group": "", "wgcna_hit": "false", "mfuzz_hit": "false", "dtu_hit": "false", "splicing_hit": "false", "functional_annotation": ""})
    write_tsv(root / "prioritization_context.tsv", context_fields, context_rows)
    functional_rows = [{"gene_id": row["gene_id"], "term": f"SYN_PATHWAY_{(index % 10) + 1:02d}", "description": "deterministic index-based annotation"} for index, row in enumerate(rows)]
    write_tsv(root / "functional_annotation.tsv", ["gene_id", "term", "description"], functional_rows)


def validate_truth(truth_path: Path, manifest_path: Path) -> tuple[list[dict[str, str]], dict[str, Any]]:
    fields, rows = read_tsv(truth_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    required = {"gene_id", "truth_class", "expected_regulatory_pattern", "rna_evidence_state", "rna_observation_state", "chip_evidence_state", "chip_observation_state", "source_mark", "difficulty_tier"}
    if not required.issubset(fields):
        raise ValueError(f"truth missing columns: {sorted(required - set(fields))}")
    if len(rows) != 1000 or len({row["gene_id"] for row in rows}) != 1000:
        raise ValueError("truth must contain 1,000 unique entities")
    if manifest["truth_table"]["sha256"] != sha256(truth_path):
        raise ValueError("truth checksum mismatch")
    expected = {"ACTIVATING_CONCORDANT": 200, "REPRESSIVE_CONCORDANT": 200, "ACTIVATING_DISCORDANT": 100, "REPRESSIVE_DISCORDANT": 100, "RNA_ONLY": 100, "CHIP_ONLY": 100, "NO_CHANGE_BACKGROUND": 200}
    if Counter(row["truth_class"] for row in rows) != expected:
        raise ValueError("truth class counts differ from frozen design")
    return rows, manifest


def fixture_checks(root: Path, truth_rows: list[dict[str, str]], rna_manifest: Path, chip_manifest: Path) -> dict[str, Any]:
    leakage_tokens = {"expected_regulatory_pattern", "truth_class", "candidate_priority", "difficulty_tier", "truth_label"}
    fixture_files = [path for path in root.rglob("*") if path.is_file() and "fixture_validation" not in path.name]
    leakage = []
    for path in fixture_files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        leakage.extend(f"{path.name}:{token}" for token in leakage_tokens if token in text)
    rna_de = read_tsv(root / "rna/integration_artifacts/rna_differential_expression.tsv")[1]
    chip_db = read_tsv(root / "chip/integration_artifacts/differential_binding.tsv")[1]
    annotations = read_tsv(root / "chip/integration_artifacts/peak_gene_annotation.tsv")[1]
    rna_document = json.loads(rna_manifest.read_text(encoding="utf-8"))
    chip_document = json.loads(chip_manifest.read_text(encoding="utf-8"))
    source_to_canonical = {
        row[key]: row["gene_id"]
        for row in truth_rows
        for key in ("source_rna_gene_id", "source_chip_gene_id")
        if row[key] != "NOT_APPLICABLE"
    }
    expected_rna = {row["gene_id"] for row in truth_rows if row["rna_evidence_state"] == "MEASURED"}
    expected_chip = {row["gene_id"] for row in truth_rows if row["chip_evidence_state"] == "MEASURED"}
    observed_rna = {source_to_canonical.get(row["gene_id"], "") for row in rna_de}
    observed_chip = {source_to_canonical.get(row["gene_id"], "") for row in chip_db}
    observed_annotation = {source_to_canonical.get(row["gene_id"], "") for row in annotations}
    expected_marks = {row["source_mark"] for row in truth_rows if row["source_mark"] != "NOT_APPLICABLE"}
    observed_marks = {row["mark_or_factor"] for row in annotations}
    expected_shared = {
        row["multi_gene_region_id"]
        for row in truth_rows
        if row["multi_gene_region_id"]
    }
    shared_targets: dict[str, set[str]] = defaultdict(set)
    for row in annotations:
        if row["peak_id"] in expected_shared:
            shared_targets[row["peak_id"]].add(source_to_canonical.get(row["gene_id"], ""))
    errors = []
    for label, observed, expected in (
        ("RNA entity identities", observed_rna, expected_rna),
        ("ChIP differential entity identities", observed_chip, expected_chip),
        ("ChIP annotation entity identities", observed_annotation, expected_chip),
        ("mark identities", observed_marks, expected_marks),
    ):
        if observed != expected:
            errors.append(f"{label} differ: missing={len(expected - observed)} unexpected={len(observed - expected)}")
    if Counter(row["rna_observation_state"] for row in truth_rows)["MISSING"] != sum(not row["log2FoldChange"] for row in rna_de):
        errors.append("RNA MISSING encoding count differs from frozen truth")
    if Counter(row["chip_observation_state"] for row in truth_rows)["MISSING"] != sum(not row["log2FoldChange"] for row in chip_db):
        errors.append("ChIP MISSING encoding count differs from frozen truth")
    db_keys = [(row["peak_id"], row["contrast_id"]) for row in chip_db]
    if len(db_keys) != len(set(db_keys)):
        errors.append("differential-binding fixture contains duplicate region/contrast observations")
    if any(len(shared_targets[region]) < 2 for region in expected_shared):
        errors.append("one-region-to-multiple-gene relationships were not materialized")
    references = {rna_document["reference"][key] for key in ("reference_id",)} | {chip_document["reference"][key] for key in ("reference_id",)}
    annotations_ids = {rna_document["reference"]["annotation_id"], chip_document["reference"]["annotation_id"]}
    if references != {"synthetic_integrative_v1"} or annotations_ids != {"synthetic_integrative_annotation_v1"}:
        errors.append("reference or annotation identity differs from frozen design")
    if {item["contrast_id"] for item in rna_document["contrasts"]} != {"treated_vs_control"}:
        errors.append("RNA contrast identity differs from frozen design")
    if {item["contrast_id"] for item in chip_document["contrasts"]} != {"treatment_effect"}:
        errors.append("ChIP contrast identity differs from frozen design")
    if leakage:
        errors.append(f"truth leakage detected: {leakage}")
    report = {
        "schema_version": "1.0", "type": "integrative_synthetic_fixture_validation",
        "status": "pass" if not errors else "fail", "errors": errors, "truth_leakage": leakage,
        "counts": {"truth_entities": len(truth_rows), "rna_de_rows": len(rna_de), "chip_db_rows": len(chip_db), "peak_gene_rows": len(annotations)},
        "identities": {
            "expected_rna_entities": len(expected_rna), "observed_rna_entities": len(observed_rna),
            "expected_chip_entities": len(expected_chip), "observed_chip_entities": len(observed_chip),
            "marks": sorted(observed_marks), "contexts": sorted({row["condition"] or row["stage"] for row in annotations}),
            "shared_regions": len(expected_shared), "shared_regions_with_multiple_genes": sum(len(value) >= 2 for value in shared_targets.values()),
            "rna_missing": sum(not row["log2FoldChange"] for row in rna_de), "chip_missing": sum(not row["log2FoldChange"] for row in chip_db),
        },
        "manifests": {"rna": {"path": str(rna_manifest), "sha256": sha256(rna_manifest)}, "chip": {"path": str(chip_manifest), "sha256": sha256(chip_manifest)}},
        "reference_id": "synthetic_integrative_v1", "annotation_id": "synthetic_integrative_annotation_v1",
        "contrast_semantics": {"rna": "treated_vs_control", "chip": "treatment_effect", "canonical": "condition__treated_vs_control"},
        "truth_leakage_check": "PASS" if not leakage else "FAIL",
        "fixture_validation": "PASS" if not errors else "FAIL",
    }
    dump_json(root / "fixture_validation.json", report)
    if errors:
        raise ValueError("; ".join(errors))
    return report


def write_checksums(root: Path) -> None:
    targets = sorted(path for path in root.rglob("*") if path.is_file() and path.name != "SHA256SUMS")
    (root / "SHA256SUMS").write_text("\n".join(f"{sha256(path)}  {path.relative_to(root).as_posix()}" for path in targets) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--truth", type=Path, required=True)
    parser.add_argument("--truth-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    rows, truth_manifest = validate_truth(args.truth.resolve(), args.truth_manifest.resolve())
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    rna_manifest, _ = build_rna(rows, output)
    chip_manifest, _ = build_chip(rows, output)
    build_policies(rows, output)
    report = fixture_checks(output, rows, rna_manifest, chip_manifest)
    dump_json(output / "fixture_provenance.json", {
        "schema_version": "1.0", "type": "integrative_synthetic_fixture_provenance", "scientific_target": SCIENTIFIC_TARGET,
        "truth_commit": TRUTH_COMMIT, "truth_sha256": truth_manifest["truth_table"]["sha256"], "generator": str(Path(__file__).resolve()),
        "generator_sha256": sha256(Path(__file__).resolve()), "fixture_validation": report["fixture_validation"], "scientific_execution": "not_started",
    })
    write_checksums(output)
    print(json.dumps({"TRUTH_INTEGRITY": "PASS", "SYNTHETIC_FIXTURE_VALIDATION": report["fixture_validation"], "TRUTH_LEAKAGE_CHECK": report["truth_leakage_check"], "output": str(output)}, sort_keys=True))


if __name__ == "__main__":
    main()
