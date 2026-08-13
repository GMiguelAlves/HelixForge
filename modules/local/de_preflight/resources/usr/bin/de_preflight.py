#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import hashlib
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


def matrix_rank(matrix: list[list[float]], tolerance: float = 1e-10) -> int:
    work = [row[:] for row in matrix]
    rows, columns = len(work), len(work[0]) if work else 0
    rank = 0
    for column in range(columns):
        pivot = max(range(rank, rows), key=lambda row: abs(work[row][column]), default=rank)
        if rank >= rows or abs(work[pivot][column]) <= tolerance:
            continue
        work[rank], work[pivot] = work[pivot], work[rank]
        pivot_value = work[rank][column]
        work[rank] = [value / pivot_value for value in work[rank]]
        for row in range(rows):
            if row != rank and abs(work[row][column]) > tolerance:
                factor = work[row][column]
                work[row] = [a - factor * b for a, b in zip(work[row], work[rank])]
        rank += 1
        if rank == rows:
            break
    return rank


def design_matrix(rows: list[dict[str, str]], fields: list[str]) -> list[list[float]]:
    levels = {field: sorted({row[field] for row in rows}) for field in fields}
    return [
        [1.0] + [
            1.0 if row[field] == level else 0.0
            for field in fields for level in levels[field][1:]
        ]
        for row in rows
    ]


def read_counts(path: Path) -> tuple[list[str], list[str], bool]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle, delimiter="\t")
        header = next(reader, None)
        if not header or len(header) < 2:
            raise ValueError("count matrix must contain gene_id and at least one sample")
        sample_ids = header[1:]
        if any(not value for value in sample_ids) or len(sample_ids) != len(set(sample_ids)):
            raise ValueError("count matrix sample IDs must be non-empty and unique")
        genes: list[str] = []
        has_fractional = False
        for line_number, row in enumerate(reader, start=2):
            if len(row) != len(header):
                raise ValueError(f"count row {line_number} has {len(row)} fields; expected {len(header)}")
            if not row[0]:
                raise ValueError(f"count row {line_number} has an empty gene ID")
            for value in row[1:]:
                try:
                    number = float(value)
                except ValueError as error:
                    raise ValueError(f"non-numeric count at row {line_number}") from error
                if not math.isfinite(number):
                    raise ValueError(f"non-finite count at row {line_number}")
                if number < 0:
                    raise ValueError(f"negative count at row {line_number}")
                has_fractional = has_fractional or not number.is_integer()
            genes.append(row[0])
    if len(genes) != len(set(genes)):
        raise ValueError("count matrix contains duplicated gene IDs")
    return sample_ids, genes, has_fractional


def read_samples(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fields = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]
    if "import_id" not in fields:
        raise ValueError("sample metadata must contain import_id")
    import_ids = [row.get("import_id", "") for row in rows]
    if any(not value for value in import_ids):
        raise ValueError("sample metadata contains an empty import_id")
    duplicates = [value for value, count in Counter(import_ids).items() if count > 1]
    if duplicates:
        raise ValueError("sample metadata contains duplicated import_id values: " + ", ".join(duplicates[:20]))
    return fields, rows


def verify_manifest(path: Path, counts: Path, samples: Path) -> dict[str, object]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("type") != "import":
        raise ValueError("manifest is not an Import API manifest")
    for role, artifact in (("counts", counts), ("metadata", samples)):
        item = document.get("artifacts", {}).get(role)
        if not isinstance(item, dict) or not item.get("available", False):
            raise ValueError(f"Import manifest does not expose available {role}")
        expected = str(item.get("sha256", ""))
        observed = sha256(artifact)
        if expected and expected != observed:
            raise ValueError(f"{role} checksum mismatch: {expected} != {observed}")
    return document


def write_table(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
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
    if manifest.get("provider") == "salmon":
        import_parameters = manifest.get("parameters", {})
        counts_mode = import_parameters.get("countsFromAbundance")
        library_protocol = import_parameters.get("libraryProtocol")
        valid_mode = (
            library_protocol == "full_length" and counts_mode in ("scaledTPM", "lengthScaledTPM")
        ) or (library_protocol == "three_prime" and counts_mode == "no")
        if not valid_mode:
            raise ValueError(
                "Salmon matrix-based DE requires full_length with scaledTPM/lengthScaledTPM, or "
                "three_prime with countsFromAbundance=no; original full-length counts require a "
                "future tximport offset-aware provider"
            )
    sample_ids, genes, has_fractional = read_counts(args.counts)
    sample_fields, sample_rows = read_samples(args.samples)
    sample_by_id = {row["import_id"]: row for row in sample_rows}
    if set(sample_ids) != set(sample_by_id):
        raise ValueError(
            "count/metadata sample mismatch; "
            f"without_metadata={sorted(set(sample_ids) - set(sample_by_id))[:20]}, "
            f"without_counts={sorted(set(sample_by_id) - set(sample_ids))[:20]}"
        )
    ordered_samples = [sample_by_id[value] for value in sample_ids]

    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    if str(spec.get("schema_version")) != "1.0":
        raise ValueError("unsupported Differential Expression specification version")
    if spec.get("provider") != "deseq2" or str(spec.get("test", "")).lower() != "wald":
        raise ValueError("Differential Expression API 1.0 supports provider=deseq2 and test=wald only")
    correction = str(spec.get("correction", "raw"))
    if correction != "raw":
        raise ValueError(
            "Differential Expression accepts only uncorrected Import API counts; "
            "batch-corrected matrices are exploratory artifacts"
        )

    design = spec.get("design")
    if not isinstance(design, dict):
        raise ValueError("analysis specification requires an explicit design object")
    variable = str(design.get("variable", ""))
    covariates = [str(value) for value in design.get("covariates", [])]
    formula = str(design.get("formula", ""))
    if not variable or variable in covariates or len(covariates) != len(set(covariates)):
        raise ValueError("design variable and covariates must be explicit, distinct, and unique")
    fields = covariates + [variable]
    missing_fields = [field for field in fields if field not in sample_fields]
    if missing_fields:
        raise ValueError("design fields missing from sample metadata: " + ", ".join(missing_fields))
    expected_formula = "~ " + " + ".join(fields)
    if formula != expected_formula:
        raise ValueError(f"design formula must match declared order exactly: {expected_formula}")
    for row in ordered_samples:
        missing = [field for field in fields if row.get(field) is None or row.get(field, "").strip() == ""]
        if missing:
            raise ValueError(f"sample {row['import_id']} has missing design values: {', '.join(missing)}")

    parameters = spec.get("parameters")
    if not isinstance(parameters, dict):
        raise ValueError("analysis specification requires explicit parameters")
    alpha = float(parameters.get("alpha"))
    lfc_threshold = float(parameters.get("lfc_threshold"))
    min_replicates = int(parameters.get("min_replicates"))
    non_integer_counts = str(parameters.get("non_integer_counts", ""))
    if not (0 < alpha < 1) or lfc_threshold < 0 or min_replicates < 1:
        raise ValueError("invalid DE threshold parameters")
    if non_integer_counts not in ("error", "round"):
        raise ValueError("parameters.non_integer_counts must be error or round")
    if has_fractional and non_integer_counts == "error":
        raise ValueError("count matrix contains fractional values but non_integer_counts=error")

    filter_spec = spec.get("filter")
    if not isinstance(filter_spec, dict) or filter_spec.get("method") not in ("none", "total_count"):
        raise ValueError("filter must explicitly select method=none or method=total_count")
    if filter_spec["method"] == "total_count":
        if filter_spec.get("operator") not in (">", ">=") or float(filter_spec.get("threshold", -1)) < 0:
            raise ValueError("total_count filter requires a non-negative threshold and operator > or >=")

    contrasts = spec.get("contrasts")
    if not isinstance(contrasts, list) or not contrasts:
        raise ValueError("analysis specification requires at least one explicit contrast")
    contrast_ids: set[str] = set()
    levels = Counter(row[variable] for row in ordered_samples)
    validated_contrasts: list[dict[str, object]] = []
    for order, item in enumerate(contrasts, start=1):
        contrast_id = str(item.get("id", ""))
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", contrast_id) or contrast_id in contrast_ids:
            raise ValueError(f"contrast id must be unique and filename-safe: {contrast_id!r}")
        contrast_ids.add(contrast_id)
        if item.get("factor") != variable:
            raise ValueError(f"contrast {contrast_id} factor must equal design variable {variable}")
        numerator, denominator = str(item.get("numerator", "")), str(item.get("denominator", ""))
        if not numerator or not denominator or numerator == denominator:
            raise ValueError(f"contrast {contrast_id} must declare distinct numerator and denominator")
        unavailable = [level for level in (numerator, denominator) if level not in levels]
        if unavailable:
            raise ValueError(f"contrast {contrast_id} references unavailable levels: {unavailable}")
        under_replicated = [level for level in (numerator, denominator) if levels[level] < min_replicates]
        if under_replicated:
            raise ValueError(f"contrast {contrast_id} has fewer than {min_replicates} replicates: {under_replicated}")
        validated_contrasts.append({
            "id": contrast_id,
            "factor": variable,
            "numerator": numerator,
            "denominator": denominator,
            "description": str(item.get("description") or f"{numerator} versus {denominator}"),
            "direction": str(item.get("direction") or f"{numerator}/{denominator}"),
            "order": order,
        })

    matrix = design_matrix(ordered_samples, fields)
    if matrix_rank(matrix) < len(matrix[0]):
        raise ValueError("design matrix is rank deficient")

    output = args.output_dir
    models_dir, contrasts_dir = output / "model_specs", output / "contrast_specs"
    models_dir.mkdir(parents=True, exist_ok=True)
    contrasts_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(args.counts, output / "validated_counts.tsv")
    private_rowname = "__rowname"
    validated_fields = sample_fields + ([private_rowname] if private_rowname not in sample_fields else [])
    preserved_rows = []
    for sample_id, row in zip(sample_ids, ordered_samples):
        preserved = dict(row)
        preserved[private_rowname] = sample_id
        preserved_rows.append(preserved)
    write_table(output / "validated_samples.tsv", validated_fields, preserved_rows)

    analysis_id = str(spec.get("analysis_id", ""))
    if not analysis_id:
        raise ValueError("analysis_id is required")
    model_id = f"{analysis_id}.{variable}"
    model = {
        "schema_version": "1.0", "model_id": model_id, "model_order": 1,
        "analysis_id": analysis_id, "scope": str(spec.get("scope", "all_projects")),
        "correction": correction, "provider": "deseq2",
        "test": "wald", "variable": variable, "covariates": covariates,
        "formula": formula, "valid_levels": sorted(levels), "filter": filter_spec,
        "parameters": {"alpha": alpha, "lfc_threshold": lfc_threshold,
                       "min_replicates": min_replicates, "non_integer_counts": non_integer_counts},
        "target_dir": str(spec.get("target_dir", "")),
        "input": {"import_manifest_sha256": sha256(args.manifest),
                  "counts_sha256": sha256(args.counts), "sample_metadata_sha256": sha256(args.samples),
                  "import_provider": manifest.get("provider", "")},
    }
    safe_model_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", model_id)
    (models_dir / f"{safe_model_id}.json").write_text(json.dumps(model, sort_keys=True, separators=(",", ":")) + "\n")
    for contrast in validated_contrasts:
        safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(contrast["id"]))
        document = {"model_id": model_id, **contrast}
        (contrasts_dir / f"{safe_model_id}--{safe_id}.json").write_text(json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n")

    write_table(output / "skipped_models.tsv",
                ["analysis_id", "variable", "contrast", "status", "n_samples", "n_genes", "n_significant"], [])
    print(json.dumps({"schema_version": "1.0", "status": "valid", "analysis_id": analysis_id,
                      "samples": len(sample_ids), "genes": len(genes), "models": 1,
                      "contrasts": len(validated_contrasts), "skipped_models": 0,
                      "counts_sha256": sha256(args.counts), "sample_metadata_sha256": sha256(args.samples),
                      "import_manifest_sha256": sha256(args.manifest), "analysis_spec_sha256": sha256(args.spec)},
                     sort_keys=True))


if __name__ == "__main__":
    main()
