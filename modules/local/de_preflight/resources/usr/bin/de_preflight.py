#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
import re
import shutil
from collections import Counter
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sanitize(value: object) -> str:
    text = "" if value is None else str(value)
    if text == "":
        text = "unknown"
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", text)
    text = re.sub(r"^_+|_+$", "", text)
    return text or "unknown"


def matrix_rank(matrix: list[list[float]], tolerance: float = 1e-10) -> int:
    work = [row[:] for row in matrix]
    rows = len(work)
    columns = len(work[0]) if rows else 0
    rank = 0
    for column in range(columns):
        pivot = max(range(rank, rows), key=lambda row: abs(work[row][column]), default=rank)
        if rank >= rows or abs(work[pivot][column]) <= tolerance:
            continue
        work[rank], work[pivot] = work[pivot], work[rank]
        pivot_value = work[rank][column]
        work[rank] = [value / pivot_value for value in work[rank]]
        for row in range(rows):
            if row == rank:
                continue
            factor = work[row][column]
            if abs(factor) > tolerance:
                work[row] = [a - factor * b for a, b in zip(work[row], work[rank])]
        rank += 1
        if rank == rows:
            break
    return rank


def design_matrix(rows: list[dict[str, str]], fields: list[str]) -> list[list[float]]:
    levels = {field: sorted({row[field] for row in rows}) for field in fields}
    matrix: list[list[float]] = []
    for row in rows:
        encoded = [1.0]
        for field in fields:
            encoded.extend(1.0 if row[field] == level else 0.0 for level in levels[field][1:])
        matrix.append(encoded)
    return matrix


def read_counts(path: Path) -> tuple[list[str], list[str], list[list[str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle, delimiter="\t")
        header = next(reader, None)
        if not header or len(header) < 2:
            raise ValueError("count matrix must contain gene_id and at least one sample")
        sample_ids = header[1:]
        if any(not sample_id for sample_id in sample_ids):
            raise ValueError("count matrix contains an empty sample ID")
        if len(sample_ids) != len(set(sample_ids)):
            raise ValueError("count matrix contains duplicated sample IDs")
        genes: list[str] = []
        rows: list[list[str]] = []
        for line_number, row in enumerate(reader, start=2):
            if len(row) != len(header):
                raise ValueError(f"count row {line_number} has {len(row)} fields; expected {len(header)}")
            gene_id = row[0]
            if not gene_id:
                raise ValueError(f"count row {line_number} has an empty gene ID")
            for value in row[1:]:
                try:
                    number = float(value)
                except ValueError as error:
                    raise ValueError(f"non-numeric count at row {line_number}") from error
                if not math.isfinite(number):
                    raise ValueError(f"non-finite count at row {line_number}")
            genes.append(gene_id)
            rows.append(row)
    if len(genes) != len(set(genes)):
        raise ValueError("count matrix contains duplicated gene IDs")
    return sample_ids, genes, rows


def read_samples(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fields = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]
    if "import_id" not in fields:
        raise ValueError("sample metadata must contain import_id")
    import_ids = [row.get("import_id", "") for row in rows]
    if any(not sample_id for sample_id in import_ids):
        raise ValueError("sample metadata contains an empty import_id")
    duplicates = [sample_id for sample_id, count in Counter(import_ids).items() if count > 1]
    if duplicates:
        raise ValueError("sample metadata contains duplicated import_id values: " + ", ".join(duplicates[:20]))
    return fields, rows


def verify_manifest(manifest_path: Path, counts: Path, samples: Path) -> dict[str, object]:
    document = json.loads(manifest_path.read_text(encoding="utf-8"))
    if document.get("type") != "import":
        raise ValueError("manifest is not an Import API manifest")
    artifacts = document.get("artifacts", {})
    for role, path in (("counts", counts), ("metadata", samples)):
        spec = artifacts.get(role)
        if not isinstance(spec, dict) or not spec.get("available", False):
            raise ValueError(f"Import manifest does not expose available {role}")
        expected = str(spec.get("sha256", ""))
        observed = sha256(path)
        if expected and expected != observed:
            raise ValueError(f"{role} checksum mismatch: {expected} != {observed}")
    return document


def write_table(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--counts", required=True, type=Path)
    parser.add_argument("--samples", required=True, type=Path)
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    manifest = verify_manifest(args.manifest, args.counts, args.samples)
    sample_ids, genes, _count_rows = read_counts(args.counts)
    sample_fields, sample_rows = read_samples(args.samples)
    sample_by_id = {row["import_id"]: row for row in sample_rows}
    if set(sample_ids) != set(sample_by_id):
        missing_metadata = sorted(set(sample_ids) - set(sample_by_id))
        missing_counts = sorted(set(sample_by_id) - set(sample_ids))
        raise ValueError(
            f"count/metadata sample mismatch; without_metadata={missing_metadata[:20]}, without_counts={missing_counts[:20]}"
        )
    ordered_samples = [sample_by_id[sample_id] for sample_id in sample_ids]

    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    if str(spec.get("schema_version")) != "1.0":
        raise ValueError("unsupported Differential Expression specification version")
    if spec.get("provider", "deseq2") != "deseq2":
        raise ValueError("DE_PREFLIGHT currently supports provider=deseq2")
    if spec.get("test", "wald").lower() != "wald":
        raise ValueError("Differential Expression API 1.0 supports only the legacy Wald test")

    parameters = spec.get("parameters", {})
    alpha = float(parameters.get("alpha", 0.05))
    lfc_threshold = float(parameters.get("lfc_threshold", 1))
    min_replicates = int(parameters.get("min_replicates", 2))
    min_total_count = float(parameters.get("min_total_count", 10))
    if not (0 < alpha < 1):
        raise ValueError("alpha must be between 0 and 1")
    if lfc_threshold < 0 or min_replicates < 1 or min_total_count < 0:
        raise ValueError("invalid DE threshold parameters")

    test_variables = [str(value) for value in spec.get("test_variables", [])]
    design_covariates = [str(value) for value in spec.get("design_covariates", [])]
    explicit_contrasts = spec.get("contrasts", [])
    target_dir = str(spec.get("target_dir", ""))
    analysis_id = str(spec.get("analysis_id", "all_projects_raw"))
    if not test_variables:
        raise ValueError("analysis specification has no test_variables")

    private_rowname = "__rowname"
    validated_fields = sample_fields + ([private_rowname] if private_rowname not in sample_fields else [])
    sanitized_rows: list[dict[str, str]] = []
    for sample_id, row in zip(sample_ids, ordered_samples):
        clean = {field: sanitize(row.get(field, "")) for field in sample_fields}
        clean[private_rowname] = sample_id
        sanitized_rows.append(clean)

    output = args.output_dir
    models_dir = output / "model_specs"
    contrasts_dir = output / "contrast_specs"
    models_dir.mkdir(parents=True, exist_ok=True)
    contrasts_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(args.counts, output / "validated_counts.tsv")
    write_table(output / "validated_samples.tsv", validated_fields, sanitized_rows)

    model_count = 0
    contrast_count = 0
    skipped: list[dict[str, object]] = []
    configured_contrast_ids: set[str] = set()
    for item in explicit_contrasts:
        contrast_id = str(item.get("id", ""))
        if not contrast_id or not re.fullmatch(r"[A-Za-z0-9_.-]+", contrast_id):
            raise ValueError(f"invalid explicit contrast id: {contrast_id!r}")
        if contrast_id in configured_contrast_ids:
            raise ValueError(f"duplicated contrast id: {contrast_id}")
        configured_contrast_ids.add(contrast_id)

    for model_order, variable in enumerate([value for value in test_variables if value in sample_fields], start=1):
        level_counts = Counter(row[variable] for row in sanitized_rows)
        valid_levels = sorted(level for level, count in level_counts.items() if count >= min_replicates)
        if len(valid_levels) < 2:
            skipped.append({
                "analysis_id": analysis_id,
                "variable": variable,
                "contrast": "",
                "status": "skipped_less_than_two_levels",
                "n_samples": len(sanitized_rows),
                "n_genes": len(genes),
                "n_significant": "",
            })
            continue
        selected_rows = [row for row in sanitized_rows if row[variable] in valid_levels]
        covariates = [
            covariate for covariate in design_covariates
            if covariate != variable
            and covariate in sample_fields
            and len({row[covariate] for row in selected_rows}) > 1
        ]
        fields = covariates + [variable]
        matrix = design_matrix(selected_rows, fields)
        columns = len(matrix[0]) if matrix else 0
        if matrix_rank(matrix) < columns:
            skipped.append({
                "analysis_id": analysis_id,
                "variable": variable,
                "contrast": "",
                "status": "skipped_rank_deficient_design",
                "n_samples": len(selected_rows),
                "n_genes": len(genes),
                "n_significant": "",
            })
            continue

        configured = [item for item in explicit_contrasts if item.get("factor") == variable]
        contrasts: list[dict[str, object]] = []
        if configured:
            pairs = [
                (str(item["numerator"]), str(item["denominator"]), item)
                for item in configured
            ]
        else:
            pairs = [(left, right, {}) for left, right in itertools.combinations(valid_levels, 2)]
        for order, (numerator, denominator, configured_item) in enumerate(pairs, start=1):
            if numerator == denominator:
                raise ValueError(f"contrast {variable} has identical numerator and denominator")
            if numerator not in valid_levels or denominator not in valid_levels:
                raise ValueError(
                    f"contrast {variable} references unavailable levels: {numerator}/{denominator}; valid={valid_levels}"
                )
            contrast_id = str(configured_item.get("id") or f"{variable}__{numerator}_vs_{denominator}")
            contrasts.append({
                "id": contrast_id,
                "factor": variable,
                "numerator": numerator,
                "denominator": denominator,
                "description": str(configured_item.get("description") or f"{numerator} versus {denominator}"),
                "direction": str(configured_item.get("direction") or f"{numerator}/{denominator}"),
                "order": order,
            })
        model_id = f"{analysis_id}.{variable}"
        model = {
            "schema_version": "1.0",
            "model_id": model_id,
            "model_order": model_order,
            "analysis_id": analysis_id,
            "scope": str(spec.get("scope", "all_projects")),
            "correction": str(spec.get("correction", "raw")),
            "provider": "deseq2",
            "test": "wald",
            "variable": variable,
            "covariates": covariates,
            "formula": "~ " + " + ".join(fields),
            "valid_levels": valid_levels,
            "parameters": {
                "alpha": alpha,
                "lfc_threshold": lfc_threshold,
                "min_replicates": min_replicates,
                "min_total_count": min_total_count,
            },
            "contrasts": contrasts,
            "target_dir": target_dir,
            "input": {
                "import_manifest_sha256": sha256(args.manifest),
                "counts_sha256": sha256(args.counts),
                "sample_metadata_sha256": sha256(args.samples),
                "config_sha256": sha256(args.spec),
                "import_provider": manifest.get("provider", ""),
            },
        }
        safe_model_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", model_id)
        (models_dir / f"{safe_model_id}.json").write_text(
            json.dumps(model, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        for contrast in contrasts:
            contrast_document = {"model_id": model_id, **contrast}
            safe_contrast_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(contrast["id"]))
            (contrasts_dir / f"{safe_model_id}--{safe_contrast_id}.json").write_text(
                json.dumps(contrast_document, sort_keys=True, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )
        model_count += 1
        contrast_count += len(contrasts)

    if model_count == 0 and not skipped:
        raise ValueError("none of the configured test variables exists in sample metadata")

    skipped_fields = ["analysis_id", "variable", "contrast", "status", "n_samples", "n_genes", "n_significant"]
    write_table(output / "skipped_models.tsv", skipped_fields, skipped)
    report = {
        "schema_version": "1.0",
        "status": "valid",
        "analysis_id": analysis_id,
        "samples": len(sample_ids),
        "genes": len(genes),
        "models": model_count,
        "contrasts": contrast_count,
        "skipped_models": len(skipped),
        "counts_sha256": sha256(args.counts),
        "sample_metadata_sha256": sha256(args.samples),
        "import_manifest_sha256": sha256(args.manifest),
        "analysis_spec_sha256": sha256(args.spec),
    }
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
