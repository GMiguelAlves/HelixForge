#!/usr/bin/env python3
"""Unit checks for reusable Salmon-index validation."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "modules/local/salmon_index_validate/validate_salmon_index.py"
SPEC = importlib.util.spec_from_file_location("validate_salmon_index", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def fixture(root: Path) -> tuple[Path, Path, Path]:
    index = root / "existing_index"
    index.mkdir()
    (index / "versionInfo.json").write_text(
        json.dumps({"indexVersion": 5, "auxKmerLength": 31, "salmonVersion": "1.10.3"}),
        encoding="utf-8",
    )
    (index / "info.json").write_text(json.dumps({"k": 31}), encoding="utf-8")
    (index / "seq.bin").write_bytes(b"index-content")
    transcriptome = root / "transcriptome.fa"
    transcriptome.write_text(">tx1\nACGT\n", encoding="utf-8")
    files, size_bytes = MODULE.index_inventory(index)
    manifest = root / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "transcriptome_sha256": MODULE.sha256_file(transcriptome),
                "composite_sha256": MODULE.canonical_index_sha256(index, files, index.name),
                "composite_sha256_prefix": index.name,
                "salmon_version": "1.10.3",
                "index_version": 5,
                "kmer_size": 31,
                "file_count": len(files),
                "size_bytes": size_bytes,
            }
        ),
        encoding="utf-8",
    )
    return index, transcriptome, manifest


class SalmonPrebuiltIndexTests(unittest.TestCase):
    def test_passes_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            index, transcriptome, manifest = fixture(Path(temporary))
            before = {path.name: path.read_bytes() for path in index.iterdir()}
            result = MODULE.validate(index, transcriptome, manifest, 31)
            after = {path.name: path.read_bytes() for path in index.iterdir()}
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(before, after)

    def test_rejects_wrong_transcriptome(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            index, transcriptome, manifest = fixture(Path(temporary))
            transcriptome.write_text(">tx1\nTGCA\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "transcriptome_sha256"):
                MODULE.validate(index, transcriptome, manifest, 31)

    def test_rejects_wrong_kmer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            index, transcriptome, manifest = fixture(Path(temporary))
            with self.assertRaisesRegex(ValueError, "requested_kmer_size"):
                MODULE.validate(index, transcriptome, manifest, 29)
