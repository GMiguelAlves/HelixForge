from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class SingleEndContractTest(unittest.TestCase):
    def test_modules_follow_native_layout_contract(self):
        for module in ("trim_galore_single", "merge_fastq_single"):
            root = ROOT / "modules/local" / module
            for relative in ("main.nf", "environment.yml", "meta.yml", "README.md", "tests/README.md"):
                self.assertTrue((root / relative).is_file(), f"{module}/{relative} is missing")

    def test_modules_publish_provenance_and_apply_retry_policy(self):
        for module in ("trim_galore_single", "merge_fastq_single"):
            source = (ROOT / "modules/local" / module / "main.nf").read_text(encoding="utf-8")
            self.assertIn("publishDir", source)
            self.assertIn("errorStrategy", source)
            self.assertIn("maxRetries 2", source)
            self.assertIn('"process"', source)

    def test_single_end_stub_is_part_of_release_smoke(self):
        source = (ROOT / "tests/release/run_stub_smokes.sh").read_text(encoding="utf-8")
        self.assertIn("run_single_end_stub.sh", source)

    def test_stub_layout_branches_are_not_duplicated(self):
        marker = "rnaseq_stub_layout ?: 'paired'"
        for relative in (
            "modules/local/rnaseq_context/main.nf",
            "modules/local/rnaseq_metadata/main.nf",
        ):
            source = (ROOT / relative).read_text(encoding="utf-8")
            self.assertEqual(source.count(marker), 1, relative)


if __name__ == "__main__":
    unittest.main()
