#!/usr/bin/env python3
"""Validate a candidate-gene RNA-seq report request."""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import math
import shlex
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def table(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        first = handle.readline()
        handle.seek(0)
        delimiter = "\t" if first.count("\t") >= first.count(",") else ","
        reader = csv.DictReader(handle, delimiter=delimiter)
        if not reader.fieldnames:
            raise ValueError(f"Table has no header: {path}")
        rows = list(reader)
    return list(reader.fieldnames), rows


def artifact_sha(manifest: dict, role: str) -> str | None:
    artifact = manifest.get("artifacts", {}).get(role, {})
    return artifact.get("sha256") if isinstance(artifact, dict) else None


def parse_genes(path: Path) -> tuple[int, int]:
    groups: set[str] = set()
    pairs: set[tuple[str, str]] = set()
    for line_number, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise ValueError(f"Candidate-gene line {line_number} has no ':'.")
        group, values = line.split(":", 1)
        group = group.strip()
        genes = [value.strip() for value in values.replace(";", ",").split(",") if value.strip()]
        if not group or not genes:
            raise ValueError(f"Candidate-gene line {line_number} is empty.")
        groups.add(group)
        pairs.update((group, gene) for gene in genes)
    if not pairs:
        raise ValueError("Candidate-gene file has no queries.")
    return len(groups), len(pairs)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", required=True)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--import-manifest", type=Path, required=True)
    parser.add_argument("--abundance", type=Path, required=True)
    parser.add_argument("--samples", type=Path, required=True)
    parser.add_argument("--annotation", type=Path, required=True)
    parser.add_argument("--de-results", type=Path, required=True)
    parser.add_argument("--de-manifest", type=Path, required=True)
    parser.add_argument("--genes", type=Path, required=True)
    parser.add_argument("--parameters-base64", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--environment", type=Path, required=True)
    args = parser.parse_args()

    if args.provider != "candidate_genes_v1":
        raise ValueError(f"Unsupported RNA-seq report provider: {args.provider}")
    parameters = json.loads(base64.b64decode(args.parameters_base64).decode("utf-8"))
    import_manifest = read_json(args.import_manifest)
    de_manifest = read_json(args.de_manifest)
    if import_manifest.get("type") != "import":
        raise ValueError("Report API requires an Import API manifest.")
    if de_manifest.get("type") != "differential_expression":
        raise ValueError("Report API requires a Differential Expression API manifest.")

    abundance_header, abundance_rows = table(args.abundance)
    if not abundance_header or abundance_header[0] != "gene_id" or len(abundance_header) < 2:
        raise ValueError("Abundance matrix must start with gene_id and contain samples.")
    gene_ids: set[str] = set()
    for row in abundance_rows:
        gene_id = (row.get("gene_id") or "").strip()
        if not gene_id or gene_id in gene_ids:
            raise ValueError("Abundance gene_id values must be non-empty and unique.")
        gene_ids.add(gene_id)
        for sample in abundance_header[1:]:
            try:
                value = float(row[sample])
            except (TypeError, ValueError) as error:
                raise ValueError(f"Non-numeric abundance for {gene_id}/{sample}.") from error
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"Invalid abundance for {gene_id}/{sample}.")

    sample_header, sample_rows = table(args.samples)
    if "import_id" not in sample_header:
        raise ValueError("Sample table requires import_id.")
    import_ids = [(row.get("import_id") or "").strip() for row in sample_rows]
    if import_ids != abundance_header[1:]:
        raise ValueError("Sample table import_id order must match abundance columns exactly.")

    de_header, de_rows = table(args.de_results)
    required_de = {"gene_id", "log2FoldChange", "padj"}
    if not required_de.issubset(de_header):
        raise ValueError(f"DE results missing columns: {sorted(required_de - set(de_header))}")
    group_count, query_count = parse_genes(args.genes)

    abundance_hash = sha256(args.abundance)
    metadata_hash = sha256(args.samples)
    if import_manifest.get("status") != "stub":
        expected_abundance = artifact_sha(import_manifest, "abundance")
        expected_metadata = artifact_sha(import_manifest, "metadata")
        if expected_abundance and expected_abundance != abundance_hash:
            raise ValueError("Abundance checksum differs from Import API manifest.")
        if expected_metadata and expected_metadata != metadata_hash:
            raise ValueError("Sample-table checksum differs from Import API manifest.")

    expression_unit = parameters.get("expression_unit") or "TPM"
    if expression_unit not in {"TPM", "CPM"}:
        raise ValueError("expression_unit must be TPM or CPM.")
    import_parameters = import_manifest.get("parameters", {})
    if not isinstance(import_parameters, dict):
        raise ValueError("Import manifest parameters must be an object.")
    ignore_tx_version = import_parameters.get("ignoreTxVersion", False)
    if not isinstance(ignore_tx_version, bool):
        raise ValueError("Import manifest ignoreTxVersion must be boolean.")
    gene_id_version_policy = "strip" if ignore_tx_version else "preserve"
    title = parameters.get("title") or "Candidate gene report"
    life_stages = parameters.get("life_stage_levels") or "unknown"
    synonyms = parameters.get("stage_synonym_map") or ""
    organism_specific = bool(parameters.get("organism_specific", False))

    context = {
        "schema_version": "1.0",
        "type": "rnaseq_report_context",
        "id": args.id,
        "provider": args.provider,
        "status": "complete",
        "parameters": {
            "title": title,
            "expression_unit": expression_unit,
            "life_stage_levels": life_stages,
            "stage_synonym_map": synonyms,
            "organism_specific": organism_specific,
            "gene_id_version_policy": gene_id_version_policy,
        },
        "sample_count": len(sample_rows),
        "gene_count": len(abundance_rows),
        "de_row_count": len(de_rows),
        "group_count": group_count,
        "query_count": query_count,
        "inputs": {
            "abundance": {"sha256": abundance_hash},
            "samples": {"sha256": metadata_hash},
            "annotation": {"sha256": sha256(args.annotation)},
            "de_results": {"sha256": sha256(args.de_results)},
            "genes": {"sha256": sha256(args.genes)},
            "import_manifest": {"sha256": sha256(args.import_manifest)},
            "de_manifest": {"sha256": sha256(args.de_manifest)},
        },
    }
    args.output.write_text(json.dumps(context, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    environment = {
        "REPORT_TITLE": title,
        "EXPRESSION_UNIT": expression_unit,
        "LIFE_STAGE_LEVELS": life_stages,
        "STAGE_SYNONYM_MAP": synonyms,
        "ORGANISM_SPECIFIC_REPORTS": "1" if organism_specific else "0",
        "GENE_ID_VERSION_POLICY": gene_id_version_policy,
    }
    args.environment.write_text(
        "".join(f"export {key}={shlex.quote(str(value))}\n" for key, value in environment.items()),
        encoding="utf-8",
    )
    print(json.dumps({"id": args.id, "samples": len(sample_rows), "genes": len(abundance_rows), "queries": query_count}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
