#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def write_tsv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        if not fields:
            handle.write("\n")
            return
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def copy_matches(source: Path, target: Path, patterns: list[str]) -> None:
    for pattern in patterns:
        for path in source.glob(pattern):
            if path.is_file():
                target.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target / path.name)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--skipped", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--models", nargs="*", type=Path, default=[])
    parser.add_argument("--contrasts", nargs="*", type=Path, default=[])
    args = parser.parse_args()

    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    output = args.output_dir
    contrast_output = output / "contrasts"
    plot_output = output / "plots"
    output.mkdir(parents=True, exist_ok=True)
    contrast_output.mkdir(exist_ok=True)
    plot_output.mkdir(exist_ok=True)

    model_order: dict[str, int] = {}
    model_stats: dict[str, dict[str, object]] = {}
    for model in args.models:
        model_spec = json.loads((model / "model_spec.json").read_text(encoding="utf-8"))
        model_order[model_spec["model_id"]] = int(model_spec.get("model_order", 0))
        model_stats[model_spec["model_id"]] = json.loads((model / "model_statistics.json").read_text(encoding="utf-8"))
        copy_matches(model, output, ["dds_*.rds", "normalized_counts_*.tsv", "dispersions_*.tsv", "coefficients_*.tsv"])
        copy_matches(model / "plots", plot_output, ["*.png"])

    contrast_records: list[tuple[int, int, Path, dict[str, object], dict[str, object]]] = []
    for contrast_dir in args.contrasts:
        model_spec = json.loads((contrast_dir / "model_spec.json").read_text(encoding="utf-8"))
        contrast_spec = json.loads((contrast_dir / "contrast_spec.json").read_text(encoding="utf-8"))
        contrast_records.append((
            int(model_spec.get("model_order", model_order.get(model_spec["model_id"], 0))),
            int(contrast_spec.get("order", 0)),
            contrast_dir,
            model_spec,
            contrast_spec,
        ))
    contrast_records.sort(key=lambda item: (item[0], item[1], str(item[4]["id"])))

    all_rows: list[dict[str, str]] = []
    common_rows: list[dict[str, str]] = []
    legacy_fields: list[str] = []
    common_fields: list[str] = []
    summary_fields, summary_rows = read_tsv(args.skipped)
    for _model_order, _contrast_order, contrast_dir, model_spec, contrast_spec in contrast_records:
        result_files = list(contrast_dir.glob("DEG_*.tsv"))
        if len(result_files) != 1:
            raise ValueError(f"expected one legacy contrast table in {contrast_dir}")
        fields, rows = read_tsv(result_files[0])
        if not legacy_fields:
            legacy_fields = fields
        all_rows.extend(rows)
        shutil.copy2(result_files[0], contrast_output / result_files[0].name)
        common_path = contrast_dir / "common_results.tsv"
        fields, rows = read_tsv(common_path)
        if not common_fields:
            common_fields = fields
        common_rows.extend(rows)
        copy_matches(contrast_dir, plot_output, ["volcano_*.png"])
        statistics = json.loads((contrast_dir / "contrast_statistics.json").read_text(encoding="utf-8"))
        summary_rows.append({
            "analysis_id": model_spec["analysis_id"],
            "variable": model_spec["variable"],
            "contrast": contrast_spec["id"],
            "status": "ok",
            "n_samples": statistics["samples"],
            "n_genes": statistics["genes"],
            "n_significant": statistics["significant"],
        })

    if not summary_fields:
        summary_fields = ["analysis_id", "variable", "contrast", "status", "n_samples", "n_genes", "n_significant"]
    write_tsv(output / "deg_summary.tsv", summary_fields, summary_rows)
    write_tsv(output / "DEGs_all_results.tsv", legacy_fields, all_rows)
    alpha = float(spec.get("parameters", {}).get("alpha", 0.05))
    lfc = float(spec.get("parameters", {}).get("lfc_threshold", 1))
    significant = [
        row for row in all_rows
        if row.get("padj", "") not in ("", "NA")
        and row.get("log2FoldChange", "") not in ("", "NA")
        and float(row["padj"]) < alpha
        and abs(float(row["log2FoldChange"])) >= lfc
    ]
    write_tsv(output / "DEGs_significant.tsv", legacy_fields, significant)
    write_tsv(output / "differential_expression_results.tsv", common_fields, common_rows)

    analysis_id = str(spec.get("analysis_id", "analysis"))
    genes_before = spec.get("genes_before_filter", "see model_statistics.json")
    design = spec.get("design", {})
    variables = str(design.get("variable", ""))
    covariates = ", ".join(str(value) for value in design.get("covariates", []))
    with (output / "analysis_summary.txt").open("w", encoding="utf-8") as handle:
        handle.write(f"Analise DEG - {analysis_id}\n==============================\n\n")
        handle.write(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        handle.write(f"Genes antes do filtro: {genes_before}\n")
        handle.write(f"Variaveis testadas: {variables}\n")
        handle.write(f"Covariaveis de design: {covariates}\n\n")
        for row in summary_rows:
            handle.write("\t".join(str(row.get(field, "")) for field in summary_fields) + "\n")

    (output / "versions.yml").write_text('"DE_AGGREGATE":\n    python: "3.11"\n', encoding="utf-8")
    artifacts = {}
    for role, name in (
        ("results", "differential_expression_results.tsv"),
        ("legacy_results", "DEGs_all_results.tsv"),
        ("significant", "DEGs_significant.tsv"),
        ("summary", "deg_summary.tsv"),
    ):
        path = output / name
        artifacts[role] = {"path": name, "sha256": sha256(path), "available": True}
    manifest = {
        "schema_version": "1.0",
        "type": "differential_expression",
        "status": "complete",
        "id": analysis_id,
        "provider": "deseq2",
        "test": "wald",
        "design": design,
        "filter": spec.get("filter", {}),
        "models": len(args.models),
        "contrasts": len(contrast_records),
        "artifacts": artifacts,
    }
    (output / "de_manifest.json").write_text(json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    (output / "differential_expression.done").write_text(
        json.dumps({"id": analysis_id, "process": "DE_AGGREGATE", "status": "complete"}, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
