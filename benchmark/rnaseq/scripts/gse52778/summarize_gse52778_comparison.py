#!/usr/bin/env python3
"""Create a compact, transparent interpretation of GSE52778 concordance."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    comparison = json.loads(args.comparison.read_text(encoding="utf-8"))
    results = comparison["comparisons"]
    de = results["de_sets_and_rankings"]
    quant_keys = sorted(key for key in results if key.startswith("quant/"))
    import_keys = sorted(key for key in results if key.startswith("import/"))

    identity_checks = {
        "eight_quantifications_compared": len(quant_keys) == 8,
        "quantification_row_identity_and_order_preserved": all(
            results[key].get("rows") == 508163 and results[key].get("same_row_order") is True
            for key in quant_keys
        ),
        "three_import_matrices_compared": len(import_keys) == 3,
        "import_gene_universe_preserved": all(
            results[key].get("rows") == 78432 for key in import_keys
        ),
    }
    descriptive_concordance = {
        "deg_jaccard_at_least_0_99": de["jaccard"] >= 0.99,
        "deg_overlap_coefficient_at_least_0_99": de["overlap_coefficient"] >= 0.99,
        "common_deg_direction_concordance_is_one":
            de["direction_concordance_common_significant"] == 1.0,
        "pvalue_rank_spearman_at_least_0_999": de["pvalue_rank_spearman"] >= 0.999,
        "top_50_overlap_at_least_0_99": de["top_n_overlap"]["50"]["fraction"] >= 0.99,
        "top_100_overlap_at_least_0_99": de["top_n_overlap"]["100"]["fraction"] >= 0.99,
        "top_250_overlap_at_least_0_99": de["top_n_overlap"]["250"]["fraction"] >= 0.99,
        "top_500_overlap_at_least_0_99": de["top_n_overlap"]["500"]["fraction"] >= 0.99,
    }
    interpreted_pass = all(identity_checks.values()) and all(descriptive_concordance.values())

    exact_failures = {
        key: {
            "rows": value.get("rows"),
            "mismatch_count": value.get("mismatch_count"),
            "maximum_absolute_delta": value.get("maximum_absolute_delta"),
            "same_row_order": value.get("same_row_order"),
        }
        for key, value in results.items()
        if value.get("status") == "fail"
    }
    document = {
        "schema_version": "1.0",
        "status": "PASS_WITH_LIMITATIONS" if interpreted_pass else "FAIL",
        "dataset": "GSE52778",
        "exact_tolerance_status": comparison["status"],
        "exact_tolerance": comparison["tolerance"],
        "exact_failures": exact_failures,
        "identity_checks": identity_checks,
        "descriptive_concordance_checks": descriptive_concordance,
        "differential_expression": de,
        "limitation": (
            "Independent Salmon execution used 8 threads while the HelixForge run used 4; "
            "strict numeric tolerance failed although artifact identities and downstream "
            "differential-expression conclusions were highly concordant."
        ),
        "interpretation_policy": (
            "Descriptive post-run interpretation accepted by project decision; it does not "
            "replace the preregistered exact numeric comparison and is not a new release gate."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": document["status"], "exact_tolerance_status": comparison["status"]}))
    return 0 if interpreted_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
