#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path


def read_matrix(path: Path) -> tuple[list[str], dict[str, dict[str, float]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        samples = [field for field in reader.fieldnames or [] if field != "gene_id"]
        values = {sample: {} for sample in samples}
        for row in reader:
            for sample in samples:
                values[sample][row["gene_id"]] = float(row[sample])
    return samples, values


def correlation(left: list[float], right: list[float]) -> float:
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    numerator = sum((x - left_mean) * (y - right_mean) for x, y in zip(left, right))
    denominator = math.sqrt(
        sum((x - left_mean) ** 2 for x in left) * sum((y - right_mean) ** 2 for y in right)
    )
    return numerator / denominator if denominator else 0.0


def require(path: Path) -> None:
    if not path.exists() or (path.is_file() and path.stat().st_size == 0):
        raise AssertionError(f"missing output: {path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("case_root", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    pipeline = args.case_root / "pipeline"
    require(args.case_root / "inputs/SYNTHETIC/multiqc_030/SYNTHETIC_multiqc_030.html")
    require(pipeline / "050-quantification/counts_matrix.tsv")
    require(pipeline / "050-quantification/tpm_matrix.tsv")
    require(pipeline / "050-quantification/length_matrix.tsv")
    require(pipeline / "050-quantification/summarized_experiment.rds")
    require(args.case_root / "results/pipeline_info/native_import/tximport/import_manifest.json")

    expected_samples, expected = read_matrix(args.case_root / "expected_counts.tsv")
    observed_samples, observed = read_matrix(pipeline / "050-quantification/counts_matrix.tsv")
    observed_sample_ids = [sample.split("__", 1)[-1] for sample in observed_samples]
    if observed_sample_ids != expected_samples:
        raise AssertionError(
            f"sample order changed: {observed_sample_ids} != {expected_samples} "
            f"(matrix columns: {observed_samples})"
        )

    sample_metrics = {}
    for sample, observed_sample in zip(expected_samples, observed_samples):
        genes = sorted(expected[sample])
        if set(genes) != set(observed[observed_sample]):
            raise AssertionError(f"gene set changed for {sample}")
        expected_values = [expected[sample][gene] for gene in genes]
        observed_values = [observed[observed_sample][gene] for gene in genes]
        pearson = correlation(expected_values, observed_values)
        expected_total = sum(expected_values)
        observed_total = sum(observed_values)
        total_ratio = observed_total / expected_total
        if pearson < 0.995:
            raise AssertionError(f"low count correlation for {sample}: {pearson}")
        if not 0.98 <= total_ratio <= 1.02:
            raise AssertionError(f"count total changed for {sample}: {total_ratio}")
        sample_metrics[sample] = {"pearson": pearson, "total_ratio": total_ratio}

        quant_dir = pipeline / f"040-alignment/quants/SYNTHETIC/{sample}"
        require(quant_dir / "quant.sf")
        require(quant_dir / "cmd_info.json")
        require(quant_dir / "lib_format_counts.json")
        require(quant_dir / "aux_info/meta_info.json")
        meta_info = json.loads((quant_dir / "aux_info/meta_info.json").read_text(encoding="utf-8"))
        processed = float(meta_info["num_processed"])
        mapped = float(meta_info["num_mapped"])
        if processed <= 0 or mapped / processed < 0.98:
            raise AssertionError(f"unexpected Salmon mapping for {sample}: {mapped}/{processed}")

    de_root = pipeline / "060-deg-analysis/native"
    require(de_root)
    deg_results = list(de_root.rglob("DEG_*.tsv"))
    if not deg_results:
        raise AssertionError(f"no DESeq2 contrast result below {de_root}")
    require(deg_results[0])

    report = {
        "status": "pass",
        "samples": expected_samples,
        "matrix_columns": observed_samples,
        "genes": len(next(iter(expected.values()))),
        "sample_metrics": sample_metrics,
        "deseq2_results": [str(path.relative_to(args.case_root)) for path in deg_results],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
