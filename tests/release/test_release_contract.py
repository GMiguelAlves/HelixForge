from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class ReleaseContractTest(unittest.TestCase):
    def test_software_version_is_stable_v1(self):
        config = (ROOT / "nextflow.config").read_text(encoding="utf-8")
        match = re.search(r"^\s*version\s*=\s*'([^']+)'", config, re.MULTILINE)
        self.assertIsNotNone(match)
        self.assertEqual("1.2.0", match.group(1))
        citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
        self.assertIn('version: "1.2.0"', citation)

    def test_readme_lists_only_two_latest_releases(self):
        readme = (ROOT / 'README.md').read_text(encoding='utf-8')
        notes = re.findall(r'\[HelixForge (v[\d.]+) release notes\]', readme)
        self.assertEqual(['v1.2.0', 'v1.1.0'], notes)
        for version in notes:
            self.assertTrue((ROOT / f'docs/releases/release-notes-{version}.md').is_file())

    def test_alignment_image_pin_matches_schema_and_functional_fixture(self):
        config = (ROOT / 'nextflow.config').read_text(encoding='utf-8')
        schema = json.loads((ROOT / 'nextflow_schema.json').read_text(encoding='utf-8'))
        values = dict(re.findall(r'^\s*(\w+)\s*=\s*\x27([^\x27]+)\x27', config, re.MULTILINE))
        for parameter in ('bowtie2_container', 'bowtie2_apptainer_container',
                          'bam_samtools_container', 'bam_samtools_apptainer_container'):
            self.assertEqual(schema['properties'][parameter]['default'], values[parameter])
            self.assertIn('@sha256:', values[parameter])
        self.assertEqual(values['bowtie2_container'], values['bam_samtools_container'])
        fixture = (ROOT / 'tests/native_bowtie2_prebuilt/run_functional.py').read_text(encoding='utf-8')
        self.assertIn(values['bowtie2_container'], fixture)

    def test_v1_benchmark_summary_preserves_all_limitations(self):
        summary = json.loads((ROOT / "benchmark/v1_benchmark_summary.json").read_text(encoding="utf-8"))
        self.assertEqual("v1.0.0", summary["release"])
        self.assertEqual("PASS_WITH_LIMITATIONS", summary["overall_classification"])
        self.assertEqual({"rnaseq", "chipseq", "integrative"}, set(summary["benchmarks"]))
        self.assertTrue(all(item["classification"] == "PASS_WITH_LIMITATIONS" for item in summary["benchmarks"].values()))
        self.assertEqual(6, len(summary["preserved_limitations"]))
        for item in summary["benchmarks"].values():
            self.assertTrue((ROOT / item["report"]).is_file(), item["report"])

    def test_public_workflows_and_schema_agree(self):
        schema = json.loads((ROOT / "nextflow_schema.json").read_text(encoding="utf-8"))
        self.assertEqual(
            {"rnaseq", "chipseq", "integrative", "all"},
            set(schema["properties"]["workflow"]["enum"]),
        )
        main = (ROOT / "main.nf").read_text(encoding="utf-8")
        for workflow in schema["properties"]["workflow"]["enum"]:
            self.assertIn(f"selected == '{workflow}'", main)

    def test_schema_identifiers_are_unique_and_local_refs_resolve(self):
        identifiers: dict[str, Path] = {}
        for schema_path in sorted((ROOT / "schemas").rglob("*.json")):
            document = json.loads(schema_path.read_text(encoding="utf-8"))
            identifier = document.get("$id")
            self.assertTrue(identifier, schema_path)
            self.assertNotIn(identifier, identifiers, f"{schema_path} and {identifiers.get(identifier)}")
            identifiers[identifier] = schema_path
            for reference in re.findall(r'"\$ref"\s*:\s*"([^"]+)"', schema_path.read_text(encoding="utf-8")):
                target = reference.split("#", 1)[0]
                if target and "://" not in target:
                    self.assertTrue((schema_path.parent / target).is_file(), f"{schema_path}: {target}")

    def test_no_active_legacy_execution_surface(self):
        active = "\n".join(
            path.read_text(encoding="utf-8")
            for root in ("workflows", "subworkflows", "modules")
            for path in (ROOT / root).rglob("*.nf")
        )
        self.assertNotIn("LEGACY_STEP", active)
        self.assertFalse((ROOT / "pipelines" / "integrative" / "legacy").is_file())

    def test_doctor_and_repository_hygiene_are_versioned(self):
        doctor = ROOT / "bin" / "helixforge-doctor"
        self.assertTrue(doctor.is_file())
        self.assertIn("Nextflow 25.10.7 is required", doctor.read_text(encoding="utf-8"))
        attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
        self.assertIn("*.tsv text eol=lf", attributes)
        self.assertIn("*.bam -text", attributes)

    def test_project_license_is_declared(self):
        license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        self.assertIn("Apache License", license_text)
        self.assertIn("Version 2.0, January 2004", license_text)
        self.assertTrue((ROOT / "NOTICE").is_file())
        citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
        self.assertIn('license: "Apache-2.0"', citation)
        config = (ROOT / "nextflow.config").read_text(encoding="utf-8")
        self.assertIn("license         = 'Apache-2.0'", config)


if __name__ == "__main__":
    unittest.main()
