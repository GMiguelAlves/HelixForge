#!/usr/bin/env python3
"""Compare the GSE52778 HelixForge run with the independent same-method harness."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from compare_independent import compare, de_sets_and_rankings, helix_de, matrix_fields, rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-root", required=True, type=Path)
    parser.add_argument("--reference-root", required=True, type=Path)
    parser.add_argument("--sample-table", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    samples = [row["sample_id"] for row in rows(args.sample_table)]
    if len(samples) != 8 or len(set(samples)) != 8:
        raise ValueError("expected eight unique biological samples")

    comparisons: dict[str, object] = {}
    for sample in samples:
        comparisons[f"quant/{sample}"] = compare(
            args.case_root / f"pipeline/040-alignment/quants/gse52778_airway/{sample}/quant.sf",
            args.reference_root / f"quant/{sample}/quant.sf",
            "Name",
            [(field, field) for field in ("Length", "EffectiveLength", "TPM", "NumReads")],
        )

    for filename in ("counts_matrix.tsv", "tpm_matrix.tsv", "length_matrix.tsv"):
        left = args.case_root / f"pipeline/050-quantification/{filename}"
        right = args.reference_root / f"analysis/{filename}"
        left_fields = matrix_fields(left)
        right_fields = matrix_fields(right)
        normalized_left = [field.split("__", 1)[-1] for field in left_fields]
        if len(set(normalized_left)) != 8 or set(normalized_left) != set(samples):
            raise ValueError(f"HelixForge matrix sample set differs for {filename}")
        if set(right_fields) != set(samples):
            raise ValueError(f"independent matrix sample set differs for {filename}")
        comparisons[f"import/{filename}"] = compare(
            left, right, "gene_id", list(zip(left_fields, normalized_left))
        )

    helix_de_path = helix_de(args.case_root)
    reference_de_path = args.reference_root / "analysis/de_results.tsv"
    comparisons["differential_expression"] = compare(
        helix_de_path,
        reference_de_path,
        "gene_id",
        [
            ("baseMean", "baseMean"),
            ("log2FoldChange", "log2FoldChange"),
            ("lfcSE", "lfcSE"),
            ("statistic", "stat"),
            ("pvalue", "pvalue"),
            ("padj", "padj"),
        ],
        order_required=False,
    )
    comparisons["de_sets_and_rankings"] = de_sets_and_rankings(
        helix_de_path, reference_de_path
    )

    failed = [
        name for name, result in comparisons.items()
        if result.get("status", "pass") != "pass"
    ]
    document = {
        "schema_version": "1.0",
        "status": "pass" if not failed else "fail",
        "dataset": "GSE52778",
        "comparison": "HelixForge versus independent same-method harness",
        "tolerance": "1e-8 + 1e-6*abs(reference)",
        "samples": samples,
        "failed_comparisons": failed,
        "comparisons": comparisons,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": document["status"], "comparisons": len(comparisons)}))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
