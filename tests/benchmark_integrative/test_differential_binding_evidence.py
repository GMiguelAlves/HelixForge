from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "benchmark/integrative/scripts/real/prepare_differential_binding_evidence.py"
LAUNCHER = ROOT / "benchmark/integrative/scripts/real/slurm_prepare_differential_binding_evidence.sh"


def load_adapter():
    spec = importlib.util.spec_from_file_location("db_evidence", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DifferentialBindingEvidenceTests(unittest.TestCase):
    def test_region_catalog_is_lossless_and_ordered(self):
        adapter = load_adapter()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "db.tsv"
            target = root / "regions.bed"
            source.write_text(
                "peak_id\tchrom\tstart\tend\tlog2FoldChange\n"
                "peak.2\tchr2\t20\t29\t-1.2\n"
                "peak.1\tchr1\t1\t10\t2.1\n", encoding="utf-8")
            self.assertEqual(adapter.write_region_catalog(source, target), 2)
            self.assertEqual(target.read_text(encoding="utf-8"), "chr2\t20\t29\tpeak.2\nchr1\t1\t10\tpeak.1\n")

    def test_region_catalog_rejects_duplicate_ids(self):
        adapter = load_adapter()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "db.tsv"
            source.write_text("peak_id\tchrom\tstart\tend\np\tchr1\t1\t2\np\tchr1\t3\t4\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate"):
                adapter.write_region_catalog(source, root / "regions.bed")

    def test_frozen_annotation_policy_and_slurm_guard_are_explicit(self):
        adapter = load_adapter()
        self.assertEqual(adapter.ANNOTATION_PARAMETERS["promoter_upstream"], 2000)
        self.assertEqual(adapter.ANNOTATION_PARAMETERS["promoter_downstream"], 500)
        self.assertEqual(adapter.ANNOTATION_PARAMETERS["gene_assignment"], "first")
        text = LAUNCHER.read_text(encoding="utf-8")
        self.assertIn('[[ "$#" -ne 10 ]]', text)
        self.assertNotIn("/scratch/", text)
        self.assertNotIn("/home/", text)


if __name__ == "__main__":
    unittest.main()
