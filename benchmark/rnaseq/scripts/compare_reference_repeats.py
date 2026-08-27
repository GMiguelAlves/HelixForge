#!/usr/bin/env python3
"""Compare two independent same-method harness executions semantically."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from compare_independent import compare, de_sets_and_rankings, matrix_fields, rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--left-root", required=True, type=Path)
    parser.add_argument("--right-root", required=True, type=Path)
    parser.add_argument("--sample-table", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    samples = [row["sample_id"] for row in rows(args.sample_table)]
    comparisons: dict[str, object] = {}
    for sample in samples:
        comparisons[f"quant/{sample}"] = compare(
            args.left_root / f"quant/{sample}/quant.sf",
            args.right_root / f"quant/{sample}/quant.sf", "Name",
            [(field, field) for field in ("Length", "EffectiveLength", "TPM", "NumReads")],
        )
    for filename in ("counts_matrix.tsv", "tpm_matrix.tsv", "length_matrix.tsv"):
        left = args.left_root / f"analysis/{filename}"
        right = args.right_root / f"analysis/{filename}"
        fields = matrix_fields(left)
        if fields != matrix_fields(right) or fields != samples:
            raise ValueError(f"matrix sample order differs for {filename}")
        comparisons[f"import/{filename}"] = compare(
            left, right, "gene_id", [(field, field) for field in fields]
        )
    left_de = args.left_root / "analysis/de_results.tsv"
    right_de = args.right_root / "analysis/de_results.tsv"
    comparisons["differential_expression"] = compare(
        left_de, right_de, "gene_id",
        [("baseMean", "baseMean"), ("log2FoldChange", "log2FoldChange"),
         ("lfcSE", "lfcSE"), ("stat", "stat"), ("pvalue", "pvalue"), ("padj", "padj")],
        order_required=False,
    )
    comparisons["de_sets_and_rankings"] = de_sets_and_rankings(left_de, right_de)
    status = "pass" if all(item.get("status", "pass") == "pass"
                           for item in comparisons.values()) else "fail"
    report = {"schema_version": "1.0", "status": status,
              "tolerance": "1e-8 + 1e-6*abs(reference)",
              "samples": samples, "comparisons": comparisons}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "comparisons": len(comparisons)}))
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
