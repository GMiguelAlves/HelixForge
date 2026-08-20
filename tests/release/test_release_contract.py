from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class ReleaseContractTest(unittest.TestCase):
    def test_software_version_is_rc_candidate(self):
        config = (ROOT / "nextflow.config").read_text(encoding="utf-8")
        match = re.search(r"^\s*version\s*=\s*'([^']+)'", config, re.MULTILINE)
        self.assertIsNotNone(match)
        self.assertEqual("1.0.0-rc.1", match.group(1))

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


if __name__ == "__main__":
    unittest.main()
