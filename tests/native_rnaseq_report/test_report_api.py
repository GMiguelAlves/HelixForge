from __future__ import annotations

import base64
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "modules/local/rnaseq_report_context/resources/usr/bin/validate_rnaseq_report_context.py"
FINALIZER = ROOT / "modules/local/rnaseq_gene_report/resources/usr/bin/finalize_rnaseq_report.py"
NATIVE_REPORT = ROOT / "modules/local/rnaseq_gene_report/resources/usr/bin/gene_set_report.R"
LEGACY_REPORT = ROOT / "pipelines/rnaseq/legacy/scripts/090-search-gene/gene_set_report.R"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_text_digest(path: Path) -> str:
    content = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(content).hexdigest()


class ReportApiTest(unittest.TestCase):
    def test_native_r_provider_matches_reviewed_legacy_source(self):
        self.assertEqual(digest(NATIVE_REPORT), digest(LEGACY_REPORT))
        self.assertEqual(
            canonical_text_digest(NATIVE_REPORT),
            "36e084d6a36ec16d125ad94f5cd3e9890de265ffa63d80d01ab8e6b98ed03930",
        )

    def build_request(self, root: Path) -> list[str]:
        abundance = root / "abundance.tsv"
        samples = root / "samples.tsv"
        annotation = root / "annotation.gtf"
        de_results = root / "de.tsv"
        genes = root / "genes.txt"
        abundance.write_text("gene_id\tA__one\ngene_a\t10\n", encoding="utf-8")
        samples.write_text("dataset\tsample_id\timport_id\nA\tone\tA__one\n", encoding="utf-8")
        annotation.write_text('chr1\ttest\tgene\t1\t10\t.\t+\t.\tgene_id "gene_a";\n', encoding="utf-8")
        de_results.write_text("gene_id\tlog2FoldChange\tpadj\ngene_a\t1\t0.01\n", encoding="utf-8")
        genes.write_text("Candidates: gene_a\n", encoding="utf-8")
        import_manifest = root / "import.json"
        import_manifest.write_text(json.dumps({
            "type": "import", "status": "complete",
            "artifacts": {
                "abundance": {"sha256": digest(abundance)},
                "metadata": {"sha256": digest(samples)},
            },
        }), encoding="utf-8")
        de_manifest = root / "de.json"
        de_manifest.write_text(json.dumps({"type": "differential_expression", "status": "complete"}), encoding="utf-8")
        parameters = base64.b64encode(json.dumps({"expression_unit": "TPM"}).encode()).decode()
        return [
            sys.executable, str(VALIDATOR), "--id", "test.report", "--provider", "candidate_genes_v1",
            "--import-manifest", str(import_manifest), "--abundance", str(abundance),
            "--samples", str(samples), "--annotation", str(annotation),
            "--de-results", str(de_results), "--de-manifest", str(de_manifest),
            "--genes", str(genes), "--parameters-base64", parameters,
            "--output", str(root / "context.json"), "--environment", str(root / "report.env"),
        ]

    def test_context_accepts_matching_api_artifacts(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            subprocess.run(self.build_request(root), check=True, capture_output=True, text=True)
            context = json.loads((root / "context.json").read_text(encoding="utf-8"))
            self.assertEqual(context["sample_count"], 1)
            self.assertEqual(context["query_count"], 1)
            self.assertEqual(context["provider"], "candidate_genes_v1")

    def test_context_rejects_sample_order_mismatch(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            command = self.build_request(root)
            (root / "samples.tsv").write_text("dataset\tsample_id\timport_id\nA\tone\twrong\n", encoding="utf-8")
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("import_id order", result.stderr)

    def test_finalizer_builds_inventory_and_provenance(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            results = root / "results"
            (results / "tables").mkdir(parents=True)
            (results / "plots").mkdir()
            (results / "gene_set_report.html").write_text("<html></html>\n", encoding="utf-8")
            (results / "tables/catalog.tsv").write_text("gene_id\ngene_a\n", encoding="utf-8")
            (results / "plots/plot.png").write_bytes(b"png")
            context = root / "context.json"
            context.write_text(json.dumps({
                "parameters": {}, "sample_count": 1, "gene_count": 1, "query_count": 1,
                "inputs": {"import_manifest": {"sha256": "a"}, "de_manifest": {"sha256": "b"}},
            }), encoding="utf-8")
            session = root / "session.txt"
            session.write_text("R 4.3.3\n", encoding="utf-8")
            subprocess.run([
                sys.executable, str(FINALIZER), "--id", "test.report", "--provider", "candidate_genes_v1",
                "--context", str(context), "--results", str(results),
                "--execution", str(root / "execution.json"), "--versions", str(root / "versions.yml"),
                "--session-info", str(session), "--container", "test:1", "--git-commit", "abc",
                "--profile", "test", "--cpus", "2", "--memory-bytes", "1024", "--task-time", "1h",
                "--started-epoch", "10", "--ended-epoch", "12",
            ], check=True)
            manifest = json.loads((results / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["type"], "rnaseq_report")
            self.assertEqual(len(manifest["inventory"]), 3)
            self.assertEqual(manifest["upstream"]["de_manifest_sha256"], "b")


if __name__ == "__main__":
    unittest.main()
