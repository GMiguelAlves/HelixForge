from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class MultiqcCertificationContractTest(unittest.TestCase):
    def test_module_exposes_reusable_contract(self):
        source = (ROOT / "modules/local/multiqc/main.nf").read_text(encoding="utf-8")
        for required in (
            "process MULTIQC",
            "cache 'deep'",
            "container params.multiqc_container",
            'conda "${moduleDir}/environment.yml"',
            "emit: artifacts",
            "emit: reports",
            "emit: versions",
            "emit: status",
            "stub:",
        ):
            self.assertIn(required, source)
        self.assertIn("publishDir { meta.target_dir", source)
        self.assertNotIn("mkdir -p '${target_dir}'", source)

    def test_certification_is_real_and_version_pinned(self):
        workflow = (ROOT / ".github/workflows/multiqc-certification.yml").read_text(
            encoding="utf-8"
        )
        runner = (ROOT / "tests/native_multiqc/run_real.sh").read_text(encoding="utf-8")
        validator = (ROOT / "tests/native_multiqc/validate_real.py").read_text(
            encoding="utf-8"
        )
        image = "quay.io/biocontainers/multiqc:1.17--pyhdfd78af_1"
        self.assertIn(image, workflow)
        self.assertIn(image, runner)
        self.assertIn("docker pull", workflow)
        self.assertIn("docker image inspect", runner)
        self.assertIn("image_digest.txt", validator)
        self.assertNotIn("tests/fixtures/native_qc/bin/multiqc", runner)

    def test_fixture_contains_two_distinct_fastqc_samples(self):
        fixtures = ROOT / "tests/fixtures/native_multiqc"
        contents = [
            (fixtures / sample / "fastqc_data.txt").read_text(encoding="utf-8")
            for sample in ("sample_a_fastqc", "sample_b_fastqc")
        ]
        self.assertIn("sample_a_R1.fastq.gz", contents[0])
        self.assertIn("sample_b_R1.fastq.gz", contents[1])
        self.assertTrue(all(">>Basic Statistics\tpass" in text for text in contents))


if __name__ == "__main__":
    unittest.main()
