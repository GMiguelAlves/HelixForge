from __future__ import annotations

import csv
import json
import math
import sys
import tempfile
import unittest
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from integration.evidence.io import read_tsv  # noqa: E402
from integration.evidence.provider import build_evidence  # noqa: E402
from integration.evidence.validation import validate_evidence_manifest  # noqa: E402

FIXTURE = ROOT / "tests" / "integrative_legacy_characterization" / "fixture" / "inputs"
GOLDEN = ROOT / "tests" / "integrative_legacy_characterization" / "golden" / "core"


def artifact(artifact_id, artifact_type, reference="fixture_ref", **context):
    return {
        "artifact_id": artifact_id, "artifact_type": artifact_type, "assay": "rnaseq" if artifact_type.startswith(("gene_", "normalized", "differential_expression")) else "chipseq",
        "format": context.pop("format", "tsv"), "entity_level": context.pop("entity_level", "gene"), "reference_id": reference,
        "contrast_id": context.pop("contrast_id", None), "sample_ids": context.pop("sample_ids", []), "condition": context.pop("condition", None),
        "stage": context.pop("stage", None), "mark_or_factor": context.pop("mark_or_factor", None), "marks_or_factors": context.pop("marks_or_factors", []),
        "peak_type": context.pop("peak_type", None), "role": context.pop("role", "results"),
        "location": {"kind": "producer_relative", "path": "unused", "producer_manifest_id": artifact_id + ".producer", "base_path": None},
        "checksum": None, "source": {"type": "helixforge", "name": context.pop("tool", "fixture"), "version": "1"},
        "provenance": {"producer_workflow": "fixture", "producer_process": "FIXTURE", "software": [], "parameters": {}, "source_manifest_ids": [], "source_artifact_ids": [], "execution_metadata": None},
        "metadata": context,
    }


def manifest(assay, artifacts, contrasts=None, samples=None):
    return {
        "schema_version": "1.0", "integration_api_version": "1.0", "type": f"{assay}_run_manifest", "id": f"fixture.{assay}", "status": "complete",
        "run": {"run_id": f"fixture-{assay}"}, "reference": {"reference_id": "fixture_ref"}, "samples": samples or [],
        "contrasts": contrasts or [], "artifacts": artifacts,
    }


CONTRASTS = [
    {"contrast_id": "cercariae_vs_adult", "factor": "condition", "numerator": "cercariae", "denominator": "adult", "formula": "~ condition", "covariates": [], "assay": ["rnaseq", "chipseq"], "metadata": {}},
    {"contrast_id": "adult_vs_cercariae", "factor": "condition", "numerator": "adult", "denominator": "cercariae", "formula": "~ condition", "covariates": [], "assay": ["rnaseq", "chipseq"], "metadata": {}},
]


class RnaEvidenceTest(unittest.TestCase):
    def test_expression_de_na_and_multiple_contrasts(self):
        samples = [{"sample_id": sid, "condition": "cercariae" if sid.startswith("C") else "adult", "stage": "cercariae" if sid.startswith("C") else "adult"} for sid in ("C1", "C2", "A1", "A2")]
        artifacts = [artifact("rna.tpm", "gene_abundance"), artifact("rna.de", "differential_expression_summary", tool="DESeq2")]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            document = build_evidence(manifest("rnaseq", artifacts, CONTRASTS, samples), {"rna.tpm": FIXTURE / "tpm_matrix.tsv", "rna.de": FIXTURE / "deg_results.tsv"}, output)
            self.assertEqual("complete", document["status"])
            self.assertEqual({"expression", "differential_expression"}, {item["evidence_type"] for item in document["datasets"]})
            _, expression = read_tsv(output / "expression.tsv")
            _, differential = read_tsv(output / "differential_expression.tsv")
            self.assertEqual(32, len(expression))
            self.assertEqual(16, len(differential))
            self.assertEqual({"adult", "cercariae"}, {row["condition"] for row in expression})
            self.assertEqual({"adult_vs_cercariae", "cercariae_vs_adult"}, {row["contrast_id"] for row in differential})
            self.assertEqual("DESeq2", differential[0]["statistical_method"])

    def test_scientific_projection_matches_legacy_rna_golden(self):
        samples = [{"sample_id": sid, "condition": "cercariae" if sid.startswith("C") else "adult", "stage": "cercariae" if sid.startswith("C") else "adult"} for sid in ("C1", "C2", "A1", "A2")]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            build_evidence(manifest("rnaseq", [artifact("rna.tpm", "gene_abundance"), artifact("rna.de", "differential_expression_summary")], CONTRASTS, samples), {"rna.tpm": FIXTURE / "tpm_matrix.tsv", "rna.de": FIXTURE / "deg_results.tsv"}, output)
            _, expression = read_tsv(output / "expression.tsv")
            grouped = defaultdict(list)
            for row in expression:
                grouped[(row["source_entity_id"], row["stage"])].append(float(row["measurement"]))
            _, legacy_context = read_tsv(GOLDEN / "050-rnaseq-summary" / "rna_expression_by_context.tsv")
            for legacy in legacy_context:
                values = grouped[(legacy["gene_id"], legacy["stage_or_condition"])]
                self.assertTrue(math.isclose(sum(values) / len(values), float(legacy["mean_TPM"]), rel_tol=1e-7, abs_tol=1e-8))
            _, differential = read_tsv(output / "differential_expression.tsv")
            _, legacy_de = read_tsv(GOLDEN / "050-rnaseq-summary" / "rna_deg_long.tsv")
            projected = {(row["contrast_id"], row["source_entity_id"]): row for row in differential}
            for legacy in legacy_de:
                current = projected[(legacy["contrast_id"], legacy["gene_id"])]
                self.assertEqual(float(legacy["log2FoldChange"]), float(current["log2_fold_change"]))
                self.assertEqual(float(legacy["padj"]), float(current["padj"]))

    def test_valid_na_statistics_are_preserved_as_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            table = root / "de.tsv"
            table.write_text("gene_id\tcontrast\tlog2FoldChange\tpvalue\tpadj\ng1\ta_vs_b\t-1.2\tNA\tNA\n", encoding="utf-8")
            contrast = [{"contrast_id": "a_vs_b", "factor": "condition", "numerator": "a", "denominator": "b"}]
            build_evidence(manifest("rnaseq", [artifact("de", "differential_expression")], contrast), {"de": table}, root / "out")
            _, rows = read_tsv(root / "out" / "differential_expression.tsv")
            self.assertEqual("", rows[0]["pvalue"])
            self.assertEqual("", rows[0]["padj"])
            self.assertEqual("-1.2", rows[0]["log2_fold_change"])

    def test_unknown_contrast_and_invalid_padj_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            table = root / "de.tsv"
            table.write_text("gene_id\tcontrast\tlog2FoldChange\tpadj\ng1\tmissing\t1\t1.2\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unknown contrast_id"):
                build_evidence(manifest("rnaseq", [artifact("de", "differential_expression")], CONTRASTS), {"de": table}, root / "unknown")
            table.write_text("gene_id\tcontrast\tlog2FoldChange\tpadj\ng1\tcercariae_vs_adult\t1\t1.2\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "outside"):
                build_evidence(manifest("rnaseq", [artifact("de", "differential_expression")], CONTRASTS), {"de": table}, root / "padj")

    def test_missing_binding_and_reference_mismatch_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, "missing explicit binding"):
                build_evidence(manifest("rnaseq", [artifact("counts", "gene_counts")]), {}, root / "missing")
            bad = artifact("counts", "gene_counts", reference="other")
            with self.assertRaisesRegex(ValueError, "inconsistent reference_id"):
                build_evidence(manifest("rnaseq", [bad]), {}, root / "reference")


class ChipEvidenceTest(unittest.TestCase):
    def test_narrow_broad_consensus_and_optional_absence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            narrow = root / "narrow.bed"; narrow.write_text("chr1\t10\t20\tn1\t100\t.\t5\t4\t3\t7\n", encoding="utf-8")
            broad = root / "broad.bed"; broad.write_text("chr1\t30\t50\tb1\t90\t.\t4\t3\t2\n", encoding="utf-8")
            consensus = root / "consensus.tsv"; consensus.write_text("peak_id\tchrom\tstart\tend\tsupport\tsupport_replicates\nc1\tchr1\t10\t50\t2\t1,2\n", encoding="utf-8")
            artifacts = [
                artifact("narrow", "peak_set", format="narrowPeak", entity_level="peak", mark_or_factor="H3K27ac", condition="adult", peak_type="narrow"),
                artifact("broad", "peak_set", format="broadPeak", entity_level="peak", mark_or_factor="H3K27me3", condition="adult", peak_type="broad"),
                artifact("cons", "consensus_peaks", entity_level="peak", mark_or_factor="H3K27ac", condition="adult", peak_type="narrow", strategy="replicate_support"),
            ]
            document = build_evidence(manifest("chipseq", artifacts), {"narrow": narrow, "broad": broad, "cons": consensus}, root / "out")
            _, peaks = read_tsv(root / "out" / "peaks.tsv")
            _, consensus_rows = read_tsv(root / "out" / "consensus.tsv")
            self.assertEqual({"narrow", "broad"}, {row["peak_type"] for row in peaks})
            self.assertEqual("2", consensus_rows[0]["support"])
            self.assertFalse((root / "out" / "peak_gene.tsv").exists())
            self.assertEqual(2, len(document["datasets"]))

    def test_scientific_projection_matches_legacy_chip_golden(self):
        artifacts = [
            artifact("chip.annotation", "peak_gene_annotation", entity_level="peak", marks_or_factors=["H3K27ac", "H3K27me3", "SmHP1"]),
            artifact("chip.db", "differential_binding", entity_level="peak", contrast_id="cercariae_vs_adult", marks_or_factors=["H3K27ac", "H3K27me3"], tool="DESeq2"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build_evidence(manifest("chipseq", artifacts, [CONTRASTS[0]]), {"chip.annotation": FIXTURE / "annotated_peaks_fixture.tsv", "chip.db": FIXTURE / "differential_binding.tsv"}, root)
            _, links = read_tsv(root / "peak_gene.tsv")
            self.assertEqual(9, len(links))
            self.assertEqual({"H3K27ac", "H3K27me3", "SmHP1", "CBX"}, {row["mark_or_factor"] for row in links})
            _, db = read_tsv(root / "differential_binding.tsv")
            _, legacy = read_tsv(GOLDEN / "060-chipseq-summary" / "chip_differential_long.tsv")
            projected = {row["peak_id"]: row for row in db}
            for old in legacy:
                current = projected[old["peak_id"]]
                self.assertEqual(float(old["chip_log2FC"]), float(current["log2_fold_change"]))
                self.assertEqual(float(old["chip_padj"]), float(current["padj"]))

    def test_invalid_coordinates_and_unknown_contrast_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bad = root / "bad.bed"; bad.write_text("chr1\t20\t10\tp1\n", encoding="utf-8")
            art = artifact("bad", "peak_set", format="narrowPeak", entity_level="peak", mark_or_factor="H3K27ac", peak_type="narrow")
            with self.assertRaisesRegex(ValueError, "invalid coordinates"):
                build_evidence(manifest("chipseq", [art]), {"bad": bad}, root / "out")


class ContractTest(unittest.TestCase):
    def test_evidence_manifest_json_schema(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema is installed in CI and module environments")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            matrix = root / "matrix.tsv"; matrix.write_text("gene_id\ts1\ng1\t1\n", encoding="utf-8")
            document = build_evidence(manifest("rnaseq", [artifact("counts", "gene_counts")], samples=[{"sample_id": "s1", "condition": "a", "stage": "a"}]), {"counts": matrix}, root / "out")
            schema = json.loads((ROOT / "schemas" / "evidence" / "evidence-manifest.schema.json").read_text(encoding="utf-8"))
            jsonschema.Draft202012Validator(schema).validate(document)

    def test_supporting_and_visualization_artifacts_are_catalog_only(self):
        bam = artifact("bam", "aligned_bam", entity_level="sample")
        track = artifact("track", "signal_track", entity_level="sample")
        with tempfile.TemporaryDirectory() as directory:
            document = build_evidence(manifest("chipseq", [bam, track]), {}, Path(directory))
            classes = {item["artifact_id"]: item["classification"] for item in document["artifact_catalog"]}
            self.assertEqual("SUPPORTING_ARTIFACT", classes["bam"])
            self.assertEqual("VISUALIZATION_ARTIFACT", classes["track"])
            self.assertEqual("complete_empty", document["status"])

    def test_duplicate_gene_contrast_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            table = root / "de.tsv"
            table.write_text("gene_id\tcontrast\tlog2FoldChange\ng1\ta_vs_b\t1\ng1\ta_vs_b\t2\n", encoding="utf-8")
            contrast = [{"contrast_id": "a_vs_b", "factor": "condition", "numerator": "a", "denominator": "b"}]
            with self.assertRaisesRegex(ValueError, "duplicate scientific observation"):
                build_evidence(manifest("rnaseq", [artifact("de", "differential_expression")], contrast), {"de": table}, root / "out")


if __name__ == "__main__":
    unittest.main()
