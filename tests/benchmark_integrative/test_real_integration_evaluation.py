from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "benchmark/integrative/scripts/real/evaluate_gse133183_integration.py"
LAUNCHER = ROOT / "benchmark/integrative/scripts/real/slurm_evaluate_gse133183_integration.sh"


def load_evaluator():
    spec = importlib.util.spec_from_file_location("real_evaluation", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RealIntegrationEvaluationTests(unittest.TestCase):
    def test_selected_gene_ids_uses_frozen_symbols(self):
        evaluator = load_evaluator()
        with tempfile.TemporaryDirectory() as tmp:
            annotation = Path(tmp) / "genes.gtf"
            annotation.write_text(
                'chr1\ttest\tgene\t1\t10\t.\t+\t.\tgene_id "ENSG_FGF18.1"; gene_name "FGF18";\n'
                'chr1\ttest\tgene\t20\t30\t.\t+\t.\tgene_id "ENSG_HBB.2"; gene_name "HBB";\n',
                encoding="utf-8",
            )
            self.assertEqual(evaluator.selected_gene_ids(annotation), {"FGF18": "ENSG_FGF18.1", "HBB": "ENSG_HBB.2"})

    def test_optional_float_preserves_missingness(self):
        evaluator = load_evaluator()
        self.assertIsNone(evaluator.optional_float(""))
        self.assertIsNone(evaluator.optional_float("NA"))
        self.assertEqual(evaluator.optional_float("-1.25"), -1.25)

    def test_directional_candidates_follow_candidate_score_rank(self):
        evaluator = load_evaluator()
        ranking = [
            {"rank": "1", "canonical_entity_id": "gene.high"},
            {"rank": "2", "canonical_entity_id": "gene.mid"},
            {"rank": "3", "canonical_entity_id": "gene.low"},
        ]
        selected = evaluator.top_directional_candidates(
            ranking,
            {"CONCORDANT_ACTIVATION": {"gene.low", "gene.high"}, "CONCORDANT_REPRESSION": set()},
            {("CONCORDANT_ACTIVATION", "gene.high"): {"H3K27ac"},
             ("CONCORDANT_ACTIVATION", "gene.low"): {"H3K27me3"}},
            limit=2,
        )
        self.assertEqual(
            [row["canonical_entity_id"] for row in selected["CONCORDANT_ACTIVATION"]],
            ["gene.high", "gene.low"],
        )

    def test_launcher_is_parameterized_and_slurm_only(self):
        text = LAUNCHER.read_text(encoding="utf-8")
        self.assertIn('[[ "$#" -ne 6 ]]', text)
        self.assertIn("SLURM_JOB_ID", text)
        self.assertNotIn("/scratch/", text)
        self.assertNotIn("/home/", text)


if __name__ == "__main__":
    unittest.main()
