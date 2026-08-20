from __future__ import annotations

import json
import sys
import tempfile
import unittest
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from integration.evidence.io import read_tsv, sha256  # noqa: E402
from integration.evidence.provider import build_evidence  # noqa: E402
from integration.harmonization import build_harmonization  # noqa: E402
from integration.molecular import build_master_evidence  # noqa: E402

FIXTURE = ROOT / "tests" / "integrative_legacy_characterization" / "fixture" / "inputs"
GOLDEN = ROOT / "tests" / "integrative_legacy_characterization" / "golden" / "core"


REFERENCE = {
    "reference_id": "sm_fixture_v1", "organism": "Schistosoma mansoni", "species": "Schistosoma mansoni",
    "assembly": "fixture_v1", "genome_id": "sm_fixture_v1", "annotation_id": "annotation.fixture",
    "resources": {}, "source": {"type": "external", "name": "fixture", "version": "1"}, "metadata": {},
}
RNA_CONTRASTS = [
    {"contrast_id": "cercariae_vs_adult", "factor": "condition", "numerator": "cercariae", "denominator": "adult"},
    {"contrast_id": "adult_vs_cercariae", "factor": "condition", "numerator": "adults", "denominator": "cercaria"},
]
CHIP_CONTRASTS = [{"contrast_id": "chip_cerc_vs_adult", "factor": "condition", "numerator": "cercaria", "denominator": "adult"}]


def artifact(artifact_id, artifact_type, assay, **context):
    return {
        "artifact_id": artifact_id, "artifact_type": artifact_type, "assay": assay, "format": context.pop("format", "tsv"),
        "entity_level": context.pop("entity_level", "gene"), "reference_id": "sm_fixture_v1", "contrast_id": context.pop("contrast_id", None),
        "sample_ids": context.pop("sample_ids", []), "condition": context.pop("condition", None), "stage": context.pop("stage", None),
        "mark_or_factor": context.pop("mark_or_factor", None), "marks_or_factors": context.pop("marks_or_factors", []),
        "peak_type": context.pop("peak_type", None), "role": context.pop("role", "results"), "checksum": None,
        "location": {"kind": "producer_relative", "path": "unused", "producer_manifest_id": artifact_id + ".producer", "base_path": None},
        "source": {"type": "helixforge", "name": context.pop("tool", "fixture"), "version": "1"},
        "provenance": {"producer_workflow": assay, "producer_process": "FIXTURE", "software": [], "parameters": {}, "source_manifest_ids": [], "source_artifact_ids": [], "execution_metadata": None},
        "metadata": context,
    }


def run_manifest(assay, artifacts, contrasts, samples=None, reference=None):
    return {
        "type": f"{assay}_run_manifest", "id": f"fixture.{assay}.run", "run": {"run_id": f"fixture-{assay}"},
        "reference": reference or REFERENCE, "samples": samples or [], "contrasts": contrasts, "artifacts": artifacts,
    }


def legacy_bundles(root: Path):
    rna_dir, chip_dir = root / "rna", root / "chip"
    samples = [{"sample_id": sample, "condition": "cercariae" if sample.startswith("C") else "adult", "stage": "cercariae" if sample.startswith("C") else "adult"} for sample in ("C1", "C2", "A1", "A2")]
    rna_artifacts = [artifact("rna.tpm", "gene_abundance", "rnaseq"), artifact("rna.de", "differential_expression_summary", "rnaseq", tool="DESeq2")]
    build_evidence(run_manifest("rnaseq", rna_artifacts, RNA_CONTRASTS, samples), {"rna.tpm": FIXTURE / "tpm_matrix.tsv", "rna.de": FIXTURE / "deg_results.tsv"}, rna_dir)
    chip_artifacts = [
        artifact("chip.annotation", "peak_gene_annotation", "chipseq", entity_level="peak", marks_or_factors=["H3K27ac", "H3K27me3", "SmHP1"]),
        artifact("chip.db", "differential_binding", "chipseq", entity_level="peak", contrast_id="chip_cerc_vs_adult", marks_or_factors=["H3K27ac", "H3K27me3"], tool="DESeq2"),
    ]
    build_evidence(run_manifest("chipseq", chip_artifacts, CHIP_CONTRASTS), {"chip.annotation": FIXTURE / "annotated_peaks_fixture.tsv", "chip.db": FIXTURE / "differential_binding.tsv"}, chip_dir)
    return rna_dir, chip_dir


class LegacySemanticRegressionTest(unittest.TestCase):
    def test_gene_universe_peak_aggregation_and_values_match_legacy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rna, chip = legacy_bundles(root)
            harmonization = root / "harmonization"
            integrated = root / "integrated"
            build_harmonization(rna, chip, harmonization)
            manifest = build_master_evidence(rna, chip, harmonization, integrated)
            self.assertEqual({"canonical_genes": 8, "long_observations": 60, "peak_groups": 9}, manifest["record_counts"])

            _, entities = read_tsv(harmonization / "entity_map.tsv")
            _, legacy_entities = read_tsv(GOLDEN / "030-id-harmonization" / "gene_master_table.tsv")
            self.assertEqual({row["gene_id"] for row in legacy_entities}, {row["canonical_entity_id"] for row in entities})

            _, aggregations = read_tsv(integrated / "peak_aggregation.tsv")
            by_gene = defaultdict(lambda: [0, 0, 0, 0])
            for row in aggregations:
                values = by_gene[row["canonical_entity_id"]]
                for index, field in enumerate(("total_associated_peaks", "promoter_peaks", "gene_body_peaks", "distal_peaks")):
                    values[index] += int(row[field])
            _, legacy_peaks = read_tsv(GOLDEN / "040-peak-gene-mapping" / "gene_to_peak_summary.tsv")
            for row in legacy_peaks:
                self.assertEqual(tuple(map(int, [row["total_associated_peaks"], row["promoter_peaks"], row["gene_body_peaks"], row["distal_peaks"]])), tuple(by_gene[row["gene_id"]]))

            _, long_rows = read_tsv(integrated / "master_evidence_long.tsv")
            de = {(row["canonical_entity_id"], row["source_contrast_id"]): row for row in long_rows if row["evidence_type"] == "differential_expression"}
            _, legacy_de = read_tsv(GOLDEN / "050-rnaseq-summary" / "rna_deg_long.tsv")
            for row in legacy_de:
                current = de[(row["gene_id"], row["contrast_id"])]
                self.assertEqual(float(row["log2FoldChange"]), float(current["effect"]))
                self.assertEqual(float(row["padj"]), float(current["padj"]))

            _, master = read_tsv(integrated / "master_evidence.tsv")
            bilateral = {row["canonical_entity_id"] for row in master if row["rna_evidence_state"] == "MEASURED" and row["chip_evidence_state"] == "MEASURED"}
            self.assertEqual({"geneA", "geneB", "geneC", "geneD", "geneF", "geneG"}, bilateral)
            self.assertEqual({"geneE", "geneH"}, {row["canonical_entity_id"] for row in master if row["chip_evidence_state"] == "NO_PEAK"})

    def test_contrast_and_mark_alias_mapping(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rna, chip = legacy_bundles(root)
            build_harmonization(rna, chip, root / "harmonization")
            _, contrasts = read_tsv(root / "harmonization" / "contrast_map.tsv")
            matched = next(row for row in contrasts if row["mapping_status"] == "MATCHED")
            self.assertEqual("cercariae_vs_adult", matched["rna_contrast_ids"])
            self.assertEqual("chip_cerc_vs_adult", matched["chip_contrast_ids"])
            self.assertEqual(1, sum(row["mapping_status"] == "RNA_ONLY" for row in contrasts))
            _, marks = read_tsv(root / "harmonization" / "mark_map.tsv")
            mapping = {row["source_mark"]: row["canonical_mark"] for row in marks}
            self.assertEqual("SmHP1", mapping["CBX"])
            self.assertEqual("SmHP1", mapping["SmHP1"])


class HarmonizationRulesTest(unittest.TestCase):
    def _small_bundles(self, root: Path, rna_ids=("gene:geneA", "geneV.1"), chip_gene="aliasA"):
        rna_table = root / "rna.tsv"
        rna_table.write_text("gene_id\tS1\n" + "\n".join(f"{gene}\t1" for gene in rna_ids) + "\n", encoding="utf-8")
        de_table = root / "de.tsv"
        de_table.write_text(f"gene_id\tcontrast\tlog2FoldChange\tpvalue\tpadj\n{rna_ids[0]}\ta_vs_b\t1.2\tNA\tNA\n", encoding="utf-8")
        peak_gene = root / "peak_gene.tsv"
        peak_gene.write_text(f"peak_id\tgene_id\tcategory\tmark_or_factor\tcondition\np1\t{chip_gene}\tpromoter\tHP1\tadults\np2\tchipOnly\tdistal\tH3K27ac\tadult\np3\t{chip_gene}\tgene_body\tH3K27me3\tadult\n", encoding="utf-8")
        rna_art = artifact("rna.counts", "gene_counts", "rnaseq")
        de_art = artifact("rna.de", "differential_expression", "rnaseq", contrast_id="a_vs_b", tool="DESeq2")
        chip_art = artifact("chip.links", "peak_gene_annotation", "chipseq", entity_level="peak", mark_or_factor="HP1", condition="adults")
        rna_dir, chip_dir = root / "rna_e", root / "chip_e"
        build_evidence(run_manifest("rnaseq", [rna_art, de_art], [{"contrast_id": "a_vs_b", "factor": "condition", "numerator": "a", "denominator": "b"}], [{"sample_id": "S1", "condition": "adult", "stage": "adult"}]), {"rna.counts": rna_table, "rna.de": de_table}, rna_dir)
        build_evidence(run_manifest("chipseq", [chip_art], []), {"chip.links": peak_gene}, chip_dir)
        return rna_dir, chip_dir

    def test_explicit_alias_prefix_version_and_full_outer_join(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rna, chip = self._small_bundles(root)
            harmonization = root / "harm"
            build_harmonization(rna, chip, harmonization, {"entity_aliases": {"aliasA": "geneA"}, "strip_version_suffix": True})
            _, entities = read_tsv(harmonization / "entity_map.tsv")
            rules = {(row["source_assay"], row["source_entity_id"]): (row["canonical_entity_id"], row["normalization_rule"]) for row in entities}
            self.assertEqual(("geneA", "strip_literal_gene_prefix"), rules[("rnaseq", "gene:geneA")])
            self.assertEqual(("geneA", "explicit_alias_map"), rules[("chipseq", "aliasA")])
            self.assertEqual(("geneV", "strip_version_suffix"), rules[("rnaseq", "geneV.1")])
            build_master_evidence(rna, chip, harmonization, root / "integrated")
            _, master = read_tsv(root / "integrated" / "master_evidence.tsv")
            states = {row["canonical_entity_id"]: (row["rna_evidence_state"], row["chip_evidence_state"]) for row in master}
            self.assertEqual(("MEASURED", "MEASURED"), states["geneA"])
            self.assertEqual(("MEASURED", "NO_PEAK"), states["geneV"])
            self.assertEqual(("NOT_MEASURED", "MEASURED"), states["chipOnly"])
            _, peak_groups = read_tsv(root / "integrated" / "peak_aggregation.tsv")
            gene_a_groups = {(row["canonical_mark"], row["total_associated_peaks"]) for row in peak_groups if row["canonical_entity_id"] == "geneA"}
            self.assertEqual({("SmHP1", "1"), ("H3K27me3", "1")}, gene_a_groups)
            _, long_rows = read_tsv(root / "integrated" / "master_evidence_long.tsv")
            de = next(row for row in long_rows if row["evidence_type"] == "differential_expression")
            self.assertEqual("", de["pvalue"])
            self.assertEqual("", de["padj"])

    def test_version_collision_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rna, chip = self._small_bundles(root, ("geneV.1", "geneV.2"), "chipOnly")
            with self.assertRaisesRegex(ValueError, "version stripping causes entity collisions"):
                build_harmonization(rna, chip, root / "harm", {"strip_version_suffix": True})

    def test_reference_incompatibility_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rna, chip = self._small_bundles(root)
            manifest_path = chip / "evidence_manifest.json"
            document = json.loads(manifest_path.read_text(encoding="utf-8"))
            document["reference"]["organism"] = "Mus musculus"
            manifest_path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "organism incompatible"):
                build_harmonization(rna, chip, root / "harm")

    def test_missing_annotation_identity_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rna, chip = self._small_bundles(root)
            manifest_path = chip / "evidence_manifest.json"
            document = json.loads(manifest_path.read_text(encoding="utf-8"))
            document["reference"]["annotation_id"] = None
            manifest_path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "annotation_id incompatible"):
                build_harmonization(rna, chip, root / "harm")

    def test_broken_peak_gene_reference_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rna, chip = self._small_bundles(root)
            peak_file = root / "peaks.bed"
            peak_file.write_text("chr1\t1\t10\tp1\n", encoding="utf-8")
            peak_art = artifact("chip.peaks", "peak_set", "chipseq", format="narrowPeak", entity_level="peak", mark_or_factor="H3K27ac", peak_type="narrow")
            # Rebuild a valid bundle with a declared peak dataset, then corrupt only the association identity.
            link_file = root / "links.tsv"
            link_file.write_text("peak_id\tgene_id\tcategory\tmark_or_factor\np1\tgeneA\tpromoter\tH3K27ac\n", encoding="utf-8")
            build_evidence(run_manifest("chipseq", [peak_art, artifact("chip.links", "peak_gene_annotation", "chipseq", entity_level="peak", mark_or_factor="H3K27ac")], []), {"chip.peaks": peak_file, "chip.links": link_file}, chip)
            association = chip / "peak_gene.tsv"
            text = association.read_text(encoding="utf-8").replace("\tp1\t", "\tmissing_peak\t")
            association.write_text(text, encoding="utf-8")
            evidence_manifest = json.loads((chip / "evidence_manifest.json").read_text(encoding="utf-8"))
            next(item for item in evidence_manifest["datasets"] if item["evidence_type"] == "peak_gene")["checksum"]["value"] = sha256(association)
            (chip / "evidence_manifest.json").write_text(json.dumps(evidence_manifest), encoding="utf-8")
            harmonization = root / "harm"
            build_harmonization(rna, chip, harmonization, {"entity_aliases": {"geneA": "geneA"}})
            with self.assertRaisesRegex(ValueError, "references unknown peak"):
                build_master_evidence(rna, chip, harmonization, root / "integrated")


class ContractTest(unittest.TestCase):
    def test_manifests_validate_against_json_schema(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema is installed in CI")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rna, chip = legacy_bundles(root)
            harmonization = root / "harmonization"
            integrated = root / "integrated"
            hdoc = build_harmonization(rna, chip, harmonization)
            idoc = build_master_evidence(rna, chip, harmonization, integrated)
            for document, schema_name in ((hdoc, "harmonization-manifest.schema.json"), (idoc, "integration-manifest.schema.json")):
                schema = json.loads((ROOT / "schemas" / "integration-engine" / schema_name).read_text(encoding="utf-8"))
                jsonschema.Draft202012Validator(schema).validate(document)


if __name__ == "__main__":
    unittest.main()
