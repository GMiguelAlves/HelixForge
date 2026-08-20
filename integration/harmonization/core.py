from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from integration.evidence.io import read_json, read_tsv, safe_id, sha256, write_tsv


STAGE_ALIASES = {
    "all": "all_stages", "allstage": "all_stages", "allstages": "all_stages", "pooled": "all_stages",
    "adult": "adult", "adults": "adult", "cercaria": "cercariae", "cercariae": "cercariae",
    "egg": "eggs", "eggs": "eggs", "miracidium": "miracidia", "miracidia": "miracidia",
    "schistosomulum": "schistosomula", "schistosomula": "schistosomula",
    "sporocyst": "sporocysts", "sporocysts": "sporocysts",
}
HP1_ALIASES = {"hp1", "smhp1", "smp_179650", "smp-179650", "cbx"}
GENE_DATASETS = {"expression", "differential_expression", "peak_gene", "differential_binding"}

ENTITY_FIELDS = ["source_assay", "source_entity_id", "canonical_entity_id", "entity_type", "reference_id", "symbol", "aliases", "normalization_rule", "rule_class"]
CONTRAST_FIELDS = ["canonical_contrast_id", "factor", "numerator", "denominator", "rna_contrast_ids", "chip_contrast_ids", "mapping_status", "normalization_rule"]
MARK_FIELDS = ["source_mark", "canonical_mark", "normalization_rule", "rule_class"]


def load_evidence_bundle(directory: Path) -> tuple[dict[str, Any], dict[str, list[dict[str, str]]]]:
    root = directory.resolve()
    manifest_path = root / "evidence_manifest.json"
    if not manifest_path.is_file():
        raise ValueError(f"missing evidence manifest: {manifest_path}")
    manifest = read_json(manifest_path)
    datasets: dict[str, list[dict[str, str]]] = {}
    for item in manifest.get("datasets", []):
        target = (root / item["path"]).resolve()
        if not target.is_relative_to(root) or not target.is_file():
            raise ValueError(f"evidence dataset escapes or is missing: {item.get('path')}")
        if item.get("checksum", {}).get("value") and sha256(target) != item["checksum"]["value"]:
            raise ValueError(f"evidence dataset checksum mismatch: {item['path']}")
        _fields, rows = read_tsv(target)
        datasets[item["evidence_type"]] = rows
    return manifest, datasets


def reference_errors(rna: dict[str, Any], chip: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    left, right = rna.get("reference") or {}, chip.get("reference") or {}
    if not left or not right:
        return ["cross-assay integration requires Evidence Model 1.1 reference objects"]
    for field in ("reference_id", "genome_id", "assembly", "annotation_id"):
        if not left.get(field) or left.get(field) != right.get(field):
            errors.append(f"{field} incompatible: {left.get(field)!r} != {right.get(field)!r}")
    if not left.get("organism") or str(left.get("organism")).casefold() != str(right.get("organism")).casefold():
        errors.append(f"organism incompatible: {left.get('organism')!r} != {right.get('organism')!r}")
    return errors


def canonical_context(value: str) -> tuple[str, str, str]:
    source = str(value or "").strip()
    if not source:
        return "", "none", "SAFE_CANONICALIZATION"
    normalized = re.sub(r"[^a-z0-9]+", "", source.casefold())
    if normalized in STAGE_ALIASES:
        canonical = STAGE_ALIASES[normalized]
        rule = "exact" if source == canonical else "stage_vocabulary_v1"
        return canonical, rule, "DOMAIN_RULE" if rule != "exact" else "SAFE_CANONICALIZATION"
    return source, "exact", "SAFE_CANONICALIZATION"


def canonical_mark(value: str) -> tuple[str, str, str]:
    source = str(value or "").strip()
    normalized = re.sub(r"[^a-z0-9_-]+", "", source.casefold())
    if normalized in HP1_ALIASES:
        return "SmHP1", "schistosoma_hp1_alias_v1", "DOMAIN_RULE"
    histone = re.fullmatch(r"h([234])k([0-9]+)(me[0-3]|ac)", normalized)
    if histone:
        canonical = f"H{histone.group(1)}K{histone.group(2)}{histone.group(3)}"
        return canonical, "histone_mark_case_v1" if source != canonical else "exact", "SAFE_CANONICALIZATION"
    if source:
        return source, "exact", "SAFE_CANONICALIZATION"
    return "", "none", "SAFE_CANONICALIZATION"


def _entity(source_id: str, assay: str, reference_id: str, policy: dict[str, Any]) -> dict[str, str]:
    source = str(source_id or "").strip()
    if not source:
        raise ValueError(f"{assay} evidence contains an empty gene entity")
    aliases = policy.get("entity_aliases", {})
    symbols = policy.get("symbols", {})
    if source in aliases:
        canonical, rule, rule_class = str(aliases[source]), "explicit_alias_map", "DOMAIN_RULE"
    elif source.startswith("gene:"):
        canonical, rule, rule_class = source[5:], "strip_literal_gene_prefix", "SAFE_CANONICALIZATION"
    elif policy.get("strip_version_suffix", False) and re.search(r"\.[0-9]+$", source):
        canonical, rule, rule_class = re.sub(r"\.[0-9]+$", "", source), "strip_version_suffix", "DOMAIN_RULE"
    else:
        canonical, rule, rule_class = source, "exact", "SAFE_CANONICALIZATION"
    if not canonical:
        raise ValueError(f"entity normalization produced an empty ID for {source!r}")
    return {"source_assay": assay, "source_entity_id": source, "canonical_entity_id": canonical, "entity_type": "gene", "reference_id": reference_id, "symbol": str(symbols.get(canonical, "")), "aliases": source if source != canonical else "", "normalization_rule": rule, "rule_class": rule_class}


def _entity_rows(manifests: list[dict[str, Any]], bundles: list[dict[str, list[dict[str, str]]]], policy: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    version_groups: dict[tuple[str, str], set[str]] = defaultdict(set)
    for manifest, datasets in zip(manifests, bundles):
        assay = manifest["assay"]
        for kind in GENE_DATASETS:
            for evidence in datasets.get(kind, []):
                source = evidence.get("source_entity_id", "")
                if not source or (assay, source) in seen:
                    continue
                row = _entity(source, assay, manifest["reference_id"], policy)
                rows.append(row)
                seen.add((assay, source))
                if row["normalization_rule"] == "strip_version_suffix":
                    version_groups[(assay, row["canonical_entity_id"])].add(source)
    collisions = {key: values for key, values in version_groups.items() if len(values) > 1}
    if collisions:
        rendered = "; ".join(f"{assay}:{canonical} <- {sorted(values)}" for (assay, canonical), values in collisions.items())
        raise ValueError(f"version stripping causes entity collisions: {rendered}")
    return sorted(rows, key=lambda row: (row["canonical_entity_id"], row["source_assay"], row["source_entity_id"]))


def _contrast_rows(manifests: list[dict[str, Any]]) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
    seen_per_assay: set[tuple[str, str, str, str]] = set()
    for manifest in manifests:
        assay = manifest["assay"]
        for contrast in manifest.get("contrasts", []):
            factor = str(contrast.get("factor") or "").strip().casefold()
            numerator, nrule, _ = canonical_context(str(contrast.get("numerator") or ""))
            denominator, drule, _ = canonical_context(str(contrast.get("denominator") or ""))
            if not factor or not numerator or not denominator or numerator == denominator:
                raise ValueError(f"invalid {assay} contrast {contrast.get('contrast_id')!r}")
            key = (factor, numerator, denominator)
            duplicate_key = (assay, *key)
            if duplicate_key in seen_per_assay:
                raise ValueError(f"duplicate semantic contrast in {assay}: {key}")
            seen_per_assay.add(duplicate_key)
            item = grouped.setdefault(key, {"rnaseq": [], "chipseq": [], "rules": set()})
            item[assay].append(str(contrast["contrast_id"]))
            item["rules"].update([nrule, drule])
    rows = []
    for (factor, numerator, denominator), item in sorted(grouped.items()):
        canonical_id = safe_id(f"{factor}__{numerator}_vs_{denominator}")
        status = "MATCHED" if item["rnaseq"] and item["chipseq"] else "RNA_ONLY" if item["rnaseq"] else "CHIP_ONLY"
        rows.append({"canonical_contrast_id": canonical_id, "factor": factor, "numerator": numerator, "denominator": denominator, "rna_contrast_ids": ";".join(item["rnaseq"]), "chip_contrast_ids": ";".join(item["chipseq"]), "mapping_status": status, "normalization_rule": ";".join(sorted(item["rules"]))})
    return rows


def _mark_rows(chip_datasets: dict[str, list[dict[str, str]]]) -> list[dict[str, str]]:
    source_marks = sorted({row.get("mark_or_factor", "") for rows in chip_datasets.values() for row in rows if row.get("mark_or_factor")})
    return [{"source_mark": source, "canonical_mark": canonical_mark(source)[0], "normalization_rule": canonical_mark(source)[1], "rule_class": canonical_mark(source)[2]} for source in source_marks]


def build_harmonization(rna_dir: Path, chip_dir: Path, output: Path, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = policy or {}
    rna_manifest, rna_data = load_evidence_bundle(rna_dir)
    chip_manifest, chip_data = load_evidence_bundle(chip_dir)
    if rna_manifest.get("assay") != "rnaseq" or chip_manifest.get("assay") != "chipseq":
        raise ValueError("harmonization requires one RNA and one ChIP evidence bundle")
    errors = reference_errors(rna_manifest, chip_manifest)
    if errors:
        raise ValueError("reference incompatibility: " + "; ".join(errors))
    output.mkdir(parents=True, exist_ok=True)
    entities = _entity_rows([rna_manifest, chip_manifest], [rna_data, chip_data], policy)
    contrasts = _contrast_rows([rna_manifest, chip_manifest])
    marks = _mark_rows(chip_data)
    write_tsv(output / "entity_map.tsv", ENTITY_FIELDS, entities)
    write_tsv(output / "contrast_map.tsv", CONTRAST_FIELDS, contrasts)
    write_tsv(output / "mark_map.tsv", MARK_FIELDS, marks)
    datasets = []
    for kind, filename, count in (("entity_map", "entity_map.tsv", len(entities)), ("contrast_map", "contrast_map.tsv", len(contrasts)), ("mark_map", "mark_map.tsv", len(marks))):
        datasets.append({"dataset_type": kind, "path": filename, "records": count, "checksum": {"algorithm": "sha256", "value": sha256(output / filename)}})
    document = {"schema_version": "1.0", "harmonization_model_version": "1.0", "type": "cross_assay_harmonization", "id": f"{rna_manifest['id']}--{chip_manifest['id']}.harmonization", "status": "complete", "reference": rna_manifest["reference"], "input_evidence_manifests": [{"id": rna_manifest["id"], "assay": "rnaseq", "checksum": {"algorithm": "sha256", "value": sha256(Path(rna_dir) / "evidence_manifest.json")}}, {"id": chip_manifest["id"], "assay": "chipseq", "checksum": {"algorithm": "sha256", "value": sha256(Path(chip_dir) / "evidence_manifest.json")}}], "policy": {"entity_aliases": policy.get("entity_aliases", {}), "strip_version_suffix": bool(policy.get("strip_version_suffix", False)), "stage_vocabulary": "helixforge_stage_v1", "mark_vocabulary": "helixforge_mark_v1"}, "datasets": datasets, "provenance": {"provider": "cross_assay_harmonization", "provider_version": "1.0"}}
    (output / "harmonization_manifest.json").write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    from integration.validation import validate_harmonization
    errors = validate_harmonization(document, output)
    if errors:
        raise ValueError("invalid harmonization output: " + "; ".join(errors))
    return document
