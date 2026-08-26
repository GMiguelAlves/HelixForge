#!/usr/bin/env python3
"""Compare two clean HelixForge synthetic executions."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

from compare_independent import compare, de_sets_and_rankings, matrix_fields, rows


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def de_path(case_root: Path) -> Path:
    candidates = list((case_root / "pipeline/060-deg-analysis").rglob(
        "differential_expression_results.tsv"
    ))
    if len(candidates) != 1:
        raise ValueError(f"expected one DE table below {case_root}, found {len(candidates)}")
    return candidates[0]


def normalized_manifest(path: Path) -> dict[str, object]:
    document = copy.deepcopy(json.loads(path.read_text(encoding="utf-8")))
    document["id"] = "<volatile-run-qualified-id>"
    document["run"]["run_id"] = "<volatile-run-id>"
    document["run"]["run_name"] = "<volatile-run-name>"
    for artifact in document.get("artifacts", []):
        checksum = artifact.get("checksum")
        if isinstance(checksum, dict) and "value" in checksum:
            checksum["value"] = "<content-dependent-checksum>"
    return document


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--left-root", required=True, type=Path)
    parser.add_argument("--right-root", required=True, type=Path)
    parser.add_argument("--sample-table", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    samples = [row["sample_id"] for row in rows(args.sample_table)]
    comparisons: dict[str, object] = {}
    merged_equal = True
    for sample in samples:
        for mate in ("R1", "R2"):
            relative = f"scratch/POLYESTER_V1/trimmed_merged/{sample}_{mate}_trimmed.fastq.gz"
            left_digest = digest(args.left_root / relative)
            right_digest = digest(args.right_root / relative)
            equal = left_digest == right_digest
            merged_equal = merged_equal and equal
            comparisons[f"trimmed_fastq/{sample}/{mate}"] = {
                "status": "pass" if equal else "fail", "sha256_equal": equal,
                "left_sha256": left_digest, "right_sha256": right_digest,
            }
        comparisons[f"quant/{sample}"] = compare(
            args.left_root / f"pipeline/040-alignment/quants/POLYESTER_V1/{sample}/quant.sf",
            args.right_root / f"pipeline/040-alignment/quants/POLYESTER_V1/{sample}/quant.sf",
            "Name", [(field, field) for field in ("Length", "EffectiveLength", "TPM", "NumReads")],
        )
    for filename in ("counts_matrix.tsv", "tpm_matrix.tsv", "length_matrix.tsv"):
        left = args.left_root / f"pipeline/050-quantification/{filename}"
        right = args.right_root / f"pipeline/050-quantification/{filename}"
        left_fields, right_fields = matrix_fields(left), matrix_fields(right)
        if left_fields != right_fields:
            raise ValueError(f"matrix sample order differs for {filename}")
        comparisons[f"import/{filename}"] = compare(
            left, right, "gene_id", [(field, field) for field in left_fields]
        )
    left_de, right_de = de_path(args.left_root), de_path(args.right_root)
    comparisons["differential_expression"] = compare(
        left_de, right_de, "gene_id",
        [("baseMean", "baseMean"), ("log2FoldChange", "log2FoldChange"),
         ("lfcSE", "lfcSE"), ("statistic", "statistic"),
         ("pvalue", "pvalue"), ("padj", "padj")], order_required=False,
    )
    de_semantic = de_sets_and_rankings(left_de, right_de)
    comparisons["de_sets_and_rankings"] = de_semantic
    left_manifest = args.left_root / "results/rnaseq/rnaseq_run_manifest.json"
    right_manifest = args.right_root / "results/rnaseq/rnaseq_run_manifest.json"
    manifest_equal = normalized_manifest(left_manifest) == normalized_manifest(right_manifest)
    comparisons["manifest_structure"] = {
        "status": "pass" if manifest_equal else "fail",
        "normalization_allowlist": ["id", "run.run_id", "run.run_name",
                                    "artifacts[].checksum.value"],
        "equal": manifest_equal,
    }
    strict_status = "pass" if all(item.get("status", "pass") == "pass"
                                  for item in comparisons.values()) else "fail"
    top_equal = all(item["fraction"] == 1.0 for item in de_semantic["top_n_overlap"].values())
    semantic_status = "pass" if (
        merged_equal and manifest_equal and de_semantic["jaccard"] == 1.0
        and de_semantic["direction_concordance_common_significant"] == 1.0 and top_equal
    ) else "fail"
    report = {
        "schema_version": "1.0", "status": strict_status,
        "scientific_semantic_status": semantic_status,
        "tolerance": "1e-8 + 1e-6*abs(reference)",
        "samples": samples, "comparisons": comparisons,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": strict_status, "scientific_semantic_status": semantic_status,
                      "comparisons": len(comparisons)}))
    return 0 if strict_status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
