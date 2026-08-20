from __future__ import annotations

import json
import math
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from integration.evidence.io import read_tsv  # noqa: E402
from integration.harmonization import build_harmonization  # noqa: E402
from integration.interpretation.common import bh_adjust, number, pearson, spearman  # noqa: E402
from integration.interpretation.model import _legacy_class, _regulatory_pattern, build_regulatory_interpretation  # noqa: E402
from integration.interpretation.scoring import SCORE_COMPONENTS, _component_values, build_candidate_scores, rank_candidates  # noqa: E402
from integration.interpretation.statistics import build_cross_assay_statistics, fisher_right_tail  # noqa: E402
from integration.interpretation.validation import validate_manifest  # noqa: E402
from integration.molecular import build_master_evidence  # noqa: E402
from tests.molecular_integration.test_molecular_integration import legacy_bundles  # noqa: E402


POLICY = ROOT / "assets" / "integration" / "interpretation_policy.v1.json"
MARKS = ROOT / "assets" / "integration" / "mark_roles.v1.tsv"
CONTEXT = ROOT / "tests" / "interpretation" / "fixture" / "prioritization_context.tsv"
GOLDEN = ROOT / "tests" / "integrative_legacy_characterization" / "golden"


def run_stage5(root: Path):
    rna, chip = legacy_bundles(root)
    harmonization, integration = root / "harmonization", root / "integration"
    classification, scoring, interpretation = root / "classification", root / "scoring", root / "interpretation"
    build_harmonization(rna, chip, harmonization)
    build_master_evidence(rna, chip, harmonization, integration)
    build_regulatory_interpretation(integration, POLICY, MARKS, classification)
    build_candidate_scores(integration, classification, POLICY, CONTEXT, scoring)
    build_cross_assay_statistics(integration, classification, scoring, POLICY, MARKS, CONTEXT, interpretation)
    return integration, classification, scoring, interpretation


class RegulatoryRulesTest(unittest.TestCase):
    def test_legacy_classes_and_precedence(self):
        self.assertEqual("DEG_with_differential_peak", _legacy_class(True, True, 1, 1, 1, 3))
        self.assertEqual("DEG_with_promoter_peak", _legacy_class(True, False, 1, 1, 1, 3))
        self.assertEqual("DEG_with_gene_body_peak", _legacy_class(True, False, 0, 1, 1, 2))
        self.assertEqual("DEG_with_distal_peak", _legacy_class(True, False, 0, 0, 1, 1))
        self.assertEqual("DEG_only", _legacy_class(True, False, 0, 0, 0, 0))
        self.assertEqual("ChIP_only", _legacy_class(False, False, 1, 0, 0, 1))
        self.assertEqual("unchanged", _legacy_class(False, False, 0, 0, 0, 0))

    def test_directional_patterns(self):
        cases = [
            (("SIGNIFICANT", "MEASURED", "SIGNIFICANT", "UP", "INCREASED", "ACTIVATING"), "CONCORDANT_ACTIVATION"),
            (("SIGNIFICANT", "MEASURED", "SIGNIFICANT", "DOWN", "INCREASED", "REPRESSIVE"), "CONCORDANT_REPRESSION"),
            (("SIGNIFICANT", "MEASURED", "SIGNIFICANT", "UP", "INCREASED", "REPRESSIVE"), "DISCORDANT"),
            (("SIGNIFICANT", "NO_PEAK", "NOT_MEASURED", "UP", "", "NOT_APPLICABLE"), "RNA_ONLY"),
            (("NOT_MEASURED", "MEASURED", "SIGNIFICANT", "", "INCREASED", "ACTIVATING"), "CHIP_ONLY"),
            (("MEASURED_NOT_SIGNIFICANT", "NO_PEAK", "NOT_MEASURED", "UNCHANGED", "", "NOT_APPLICABLE"), "NO_REGULATORY_INTERPRETATION"),
            (("MEASURED_NOT_SIGNIFICANT", "NOT_MEASURED", "NOT_MEASURED", "UNCHANGED", "", "NOT_APPLICABLE"), "NO_REGULATORY_INTERPRETATION"),
            (("SIGNIFICANT", "MEASURED", "SIGNIFICANT", "UP", "INCREASED", "CONTEXT_DEPENDENT"), "INSUFFICIENT_MARK_SEMANTICS"),
        ]
        for inputs, expected in cases:
            self.assertEqual(expected, _regulatory_pattern(*inputs)[0])


class ScoreAndStatisticsUnitTest(unittest.TestCase):
    def test_score_minimum_maximum_missing_and_components(self):
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
        empty = _component_values("g0", [], [], {}, policy)
        self.assertEqual(0.0, sum(empty["components"].values()))
        de = [{"entity_type": "gene", "evidence_type": "differential_expression", "canonical_contrast_id": f"c{i}", "effect": "10", "padj": "1e-20", "source_evidence_id": f"r{i}", "canonical_mark": ""} for i in range(6)]
        db = [{"entity_type": "gene", "evidence_type": "differential_binding", "canonical_contrast_id": "c0", "effect": "10", "padj": "1e-20", "source_evidence_id": "d", "canonical_mark": mark} for mark in ("m1", "m2", "m3", "m4")]
        peaks = [{"promoter_peaks": "1", "canonical_mark": mark} for mark in ("m1", "m2", "m3", "m4")]
        context = {name: "true" for name in ("is_gene_of_interest", "is_epigenetic_machinery", "wgcna_hit", "mfuzz_hit", "dtu_hit", "splicing_hit")}
        maximum = _component_values("g1", de + db, peaks, context, policy)
        self.assertEqual(32.5, sum(maximum["components"].values()))
        self.assertEqual(set(SCORE_COMPONENTS), set(maximum["components"]))
        self.assertTrue(all(value >= 0 for value in maximum["components"].values()), "Candidate Score v1 has no legacy penalty component")

    def test_ties_are_ranked_by_statistical_support_then_gene_id(self):
        base = {"final_score": "5.0000", "legacy_evidence_class": "unchanged", "regulatory_patterns": "NO_REGULATORY_INTERPRETATION", "score_version": "1.0"}
        rows = [
            {**base, "canonical_entity_id": "geneB", "statistical_support": "2.0000"},
            {**base, "canonical_entity_id": "geneC", "statistical_support": "3.0000"},
            {**base, "canonical_entity_id": "geneA", "statistical_support": "2.0000"},
        ]
        ordered, ranking = rank_candidates(rows)
        self.assertEqual(["geneC", "geneA", "geneB"], [row["canonical_entity_id"] for row in ordered])
        self.assertEqual([1, 2, 3], [row["rank"] for row in ranking])

    def test_legacy_padj_component_rewards_non_significant_padj_below_one(self):
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
        row = {"entity_type": "gene", "evidence_type": "differential_expression", "canonical_contrast_id": "c1", "effect": "0.2", "padj": "0.6", "source_evidence_id": "r1", "canonical_mark": ""}
        details = _component_values("g", [row], [], {}, policy)
        self.assertEqual(0, details["significant_contrasts"])
        self.assertAlmostEqual(-math.log10(0.6), details["components"]["deg_significance_component"], places=12)

    def test_known_fisher_correlations_and_bh(self):
        self.assertAlmostEqual(0.5, fisher_right_tail(1, 1, 2, 4), places=12)
        self.assertAlmostEqual(1.0, pearson([1, 2, 3], [2, 4, 6]), places=12)
        self.assertAlmostEqual(-1.0, spearman([1, 2, 3], [3, 2, 1]), places=12)
        self.assertIsNone(pearson([1], [1]))
        self.assertIsNone(pearson([1, 1], [1, 2]))
        self.assertIsNone(number("NA"))
        self.assertEqual([0.03, 0.04, 0.03], [round(value, 8) for value in bh_adjust([0.01, 0.04, 0.02])])


class LegacyRegressionTest(unittest.TestCase):
    def test_classes_scores_ranking_fisher_and_correlations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _integration, classification, scoring, interpretation = run_stage5(root)
            _, classes = read_tsv(classification / "regulatory_classes.tsv")
            current_classes = {(row["canonical_entity_id"], row["source_rna_contrast_id"]): row["legacy_evidence_class"] for row in classes if row["source_rna_contrast_id"]}
            _, legacy_contrasts = read_tsv(GOLDEN / "core" / "070-integrated-tables" / "integrated_by_contrast.tsv")
            for row in legacy_contrasts:
                self.assertEqual(row["integrative_class"], current_classes[(row["gene_id"], row["contrast_id"])])
            self.assertIn("CONCORDANT_ACTIVATION", {row["regulatory_pattern"] for row in classes if row["canonical_entity_id"] == "geneA"})

            _, scores = read_tsv(scoring / "candidate_score.tsv")
            _, legacy_scores = read_tsv(GOLDEN / "scoring" / "080-candidate-scoring" / "candidate_gene_scores.tsv")
            self.assertEqual({row["gene_id"]: row["candidate_score"] for row in legacy_scores}, {row["canonical_entity_id"]: row["final_score"] for row in scores})
            _, ranking = read_tsv(scoring / "candidate_ranking.tsv")
            self.assertEqual([row["gene_id"] for row in legacy_scores], [row["canonical_entity_id"] for row in ranking])

            _, fisher = read_tsv(interpretation / "fisher_tests.tsv")
            _, legacy_fisher = read_tsv(GOLDEN / "statistics" / "080-candidate-scoring" / "mark_enrichment_tests.tsv")
            key = lambda row: (row.get("target_set"), row.get("feature_scope"), row.get("mark_or_factor") or row.get("canonical_mark"), row.get("stage_or_condition") or row.get("canonical_context"))
            current_fisher = {key(row): row for row in fisher}
            self.assertEqual(set(map(key, legacy_fisher)), set(current_fisher))
            for row in legacy_fisher:
                current = current_fisher[key(row)]
                for legacy_name, current_name in (("p_value", "pvalue"), ("q_value", "padj"), ("odds_ratio", "odds_ratio")):
                    self.assertAlmostEqual(float(row[legacy_name]), float(current[current_name]), places=7)

            _, correlations = read_tsv(interpretation / "correlations.tsv")
            corr = {(row["canonical_entity_id"], row["canonical_mark"], row["chip_metric"], row["method"]): row for row in correlations}
            _, legacy_corr = read_tsv(GOLDEN / "statistics" / "080-candidate-scoring" / "gene_mark_stage_correlations.tsv")
            for row in legacy_corr:
                for metric, legacy_prefix in (("total_associated_peaks", "total_peaks"), ("promoter_peaks", "promoter_peaks")):
                    for method in ("pearson", "spearman"):
                        expected = row[f"{method}_rna_vs_{legacy_prefix}"]
                        current = corr[(row["gene_id"], row["mark_or_factor"], metric, method)]["correlation"]
                        self.assertEqual(expected, current)

            manifest = json.loads((interpretation / "interpretation_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual([], validate_manifest(manifest, interpretation))

    def test_input_order_does_not_change_ranking(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            integration, classification, scoring, _interpretation = run_stage5(root)
            master_path = integration / "master_evidence.tsv"
            fields, rows = read_tsv(master_path)
            from integration.evidence.io import sha256, write_tsv
            write_tsv(master_path, fields, list(reversed(rows)))
            manifest_path = integration / "integration_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            next(item for item in manifest["datasets"] if item["dataset_type"] == "master_evidence")["checksum"]["value"] = sha256(master_path)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            second = root / "scoring-reordered"
            build_candidate_scores(integration, classification, POLICY, CONTEXT, second)
            self.assertEqual((scoring / "candidate_ranking.tsv").read_text(encoding="utf-8"), (second / "candidate_ranking.tsv").read_text(encoding="utf-8"))

    def test_irrelevant_gene_does_not_change_existing_scores(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            integration, _classification, scoring, _interpretation = run_stage5(root)
            original = {row["canonical_entity_id"]: row["final_score"] for row in read_tsv(scoring / "candidate_score.tsv")[1]}
            master_path = integration / "master_evidence.tsv"
            fields, rows = read_tsv(master_path)
            empty = {field: "" for field in fields}
            empty.update({"canonical_entity_id": "zzzNoEvidence", "reference_id": "sm_fixture_v1", "rna_evidence_state": "NOT_MEASURED", "chip_evidence_state": "NOT_MEASURED", "expression_observations": "0", "differential_expression_observations": "0", "peak_associations": "0", "differential_binding_observations": "0"})
            from integration.evidence.io import sha256, write_tsv
            write_tsv(master_path, fields, rows + [empty])
            manifest_path = integration / "integration_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            master_dataset = next(item for item in manifest["datasets"] if item["dataset_type"] == "master_evidence")
            master_dataset["records"] += 1
            master_dataset["checksum"]["value"] = sha256(master_path)
            manifest["record_counts"]["canonical_genes"] += 1
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            classification2, scoring2 = root / "classification-with-empty", root / "scoring-with-empty"
            build_regulatory_interpretation(integration, POLICY, MARKS, classification2)
            build_candidate_scores(integration, classification2, POLICY, CONTEXT, scoring2)
            updated = {row["canonical_entity_id"]: row["final_score"] for row in read_tsv(scoring2 / "candidate_score.tsv")[1]}
            self.assertEqual(original, {gene: updated[gene] for gene in original})
            self.assertEqual("0.0000", updated["zzzNoEvidence"])


class ContractTest(unittest.TestCase):
    def test_schemas_accept_real_outputs(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema is installed in CI")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _integration, _classification, _scoring, interpretation = run_stage5(root)
            manifest = json.loads((interpretation / "interpretation_manifest.json").read_text(encoding="utf-8"))
            schema = json.loads((ROOT / "schemas" / "interpretation" / "interpretation-manifest.schema.json").read_text(encoding="utf-8"))
            jsonschema.validate(manifest, schema)
            mappings = {
                "regulatory_classes.tsv": "regulatory-classification-record.schema.json",
                "candidate_score.tsv": "candidate-score-record.schema.json",
                "candidate_ranking.tsv": "candidate-ranking-record.schema.json",
                "fisher_tests.tsv": "fisher-test-record.schema.json",
                "correlations.tsv": "correlation-record.schema.json",
            }
            for table, schema_name in mappings.items():
                row_schema = json.loads((ROOT / "schemas" / "interpretation" / schema_name).read_text(encoding="utf-8"))
                for row in read_tsv(interpretation / table)[1]:
                    jsonschema.validate(row, row_schema)


if __name__ == "__main__":
    unittest.main()
