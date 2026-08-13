from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FullCoordinatorManifestTest(unittest.TestCase):
    def test_metadata_and_reference_manifests_are_report_compatible(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            metadata = root / "validated_metadata.tsv"
            with metadata.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["record_id", "dataset", "genome_id"], delimiter="\t")
                writer.writeheader()
                writer.writerow({"record_id": "r1", "dataset": "fixture", "genome_id": "fixture_v1"})
            validation = root / "metadata_validation.json"
            validation.write_text('{"status":"valid"}\n', encoding="utf-8")
            metadata_manifest = root / "metadata.json"
            subprocess.run([
                sys.executable, str(ROOT / "modules/local/chipseq_metadata/build_chipseq_metadata_manifest.py"),
                "--metadata", str(metadata), "--validation", str(validation), "--manifest", str(metadata_manifest),
            ], check=True)

            reference = root / "genome.fa"
            annotation = root / "annotation.gtf"
            reference.write_text(">chr1\nACGT\n", encoding="utf-8")
            annotation.write_text('chr1\tfixture\tgene\t1\t4\t.\t+\t.\tgene_id "g1";\n', encoding="utf-8")
            reference_manifest = root / "reference.json"
            reference_validation = root / "reference.validation.json"
            subprocess.run([
                sys.executable, str(ROOT / "modules/local/chipseq_reference_bundle/build_chipseq_reference_bundle.py"),
                "--reference-id", "fixture_v1.reference", "--genome-id", "fixture_v1", "--build", "fixture_v1",
                "--reference", str(reference), "--annotation", str(annotation),
                "--manifest", str(reference_manifest), "--validation", str(reference_validation),
            ], check=True)

            metadata_doc = json.loads(metadata_manifest.read_text(encoding="utf-8"))
            reference_doc = json.loads(reference_manifest.read_text(encoding="utf-8"))
            self.assertEqual(metadata_doc["dataset"], "fixture")
            self.assertEqual(metadata_doc["build"], "fixture_v1")
            self.assertEqual(reference_doc["artifacts"]["reference"]["sha256"], digest(reference))

    def test_report_inventory_is_built_from_native_manifests(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            types = [
                "chipseq_metadata", "reference_bundle", "alignment", "bam_final", "peak_calling",
                "peak_qc_summary", "consensus_idr", "differential_binding", "peak_annotation_aggregate", "track_aggregate",
            ]
            manifests = []
            artifacts = []
            semantic_types = {
                "peak_qc_summary": "peak_qc_summary.json",
                "consensus_idr": "consolidation_summary.json",
                "differential_binding": "differential_binding_summary.tsv",
                "peak_annotation_aggregate": "statistics.tsv",
                "track_aggregate": "tracks.tsv",
            }
            for index, manifest_type in enumerate(types):
                document = {
                    "schema_version": "1.0", "type": manifest_type, "id": f"fixture.{index}",
                    "dataset": "fixture", "genome_id": "fixture_v1", "build": "fixture_v1", "status": "complete",
                }
                if manifest_type in semantic_types:
                    artifact = root / semantic_types[manifest_type]
                    artifact.write_text(f"{manifest_type}\n", encoding="utf-8")
                    document["artifacts"] = {"summary": {"path": artifact.name, "sha256": digest(artifact)}}
                    artifacts.append(artifact)
                manifest = root / f"{index:02d}.{manifest_type}.json"
                manifest.write_text(json.dumps(document), encoding="utf-8")
                manifests.append(manifest)

            output = root / "report_input.json"
            meta = {"project_id": "fixture", "dataset": "fixture", "genome_id": "fixture_v1", "build": "fixture_v1"}
            import base64
            encoded = base64.b64encode(json.dumps(meta).encode()).decode()
            command = [
                sys.executable,
                str(ROOT / "modules/local/chipseq_full_report_input/resources/usr/bin/build_chipseq_full_report_input.py"),
                "--meta-base64", encoded, "--output", str(output),
            ]
            for manifest in manifests:
                command.extend(["--manifest", str(manifest)])
            for artifact in artifacts:
                command.extend(["--artifact", str(artifact)])
            subprocess.run(command, check=True)

            inventory = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(set(inventory["required_components"]), {entry["component"] for entry in inventory["components"]})
            self.assertEqual(sum(len(entry["artifacts"]) for entry in inventory["components"]), 5)


class FullCoordinatorTopologyTest(unittest.TestCase):
    def test_full_report_staging_preserves_alignment_and_final_bam_manifests(self):
        bam_index_qc = (ROOT / "modules/local/bam_index_qc/main.nf").read_text(encoding="utf-8")
        report_input = (ROOT / "modules/local/chipseq_full_report_input/main.nf").read_text(encoding="utf-8")
        self.assertIn('path("${meta.id}.bam_final.manifest.json")', bam_index_qc)
        self.assertNotIn(" > '${meta.id}.manifest.json'", bam_index_qc)
        self.assertIn("set -o pipefail", report_input)

    def test_full_mode_is_native_and_single_session(self):
        workflow = (ROOT / "workflows/chipseq.nf").read_text(encoding="utf-8")
        foundation = (ROOT / "subworkflows/local/chipseq/native_foundation.nf").read_text(encoding="utf-8")
        harness = (ROOT / "tests/slurm/run_chipseq_production_real.sh").read_text(encoding="utf-8")
        self.assertIn("chipseq_run_mode=full is exclusively native", workflow)
        self.assertIn("(run_mode == 'full' && full_native_flags.values().every", workflow)
        self.assertIn("PEAK_ANNOTATION(annotation_inputs)", foundation)
        self.assertIn("TRACK_GENERATION(individual_track_inputs.mix(aggregate_track_inputs))", foundation)
        self.assertIn(".combine(annotation_references, by: 0)", foundation)
        self.assertIn(".combine(track_references, by: 0)", foundation)
        self.assertIn("CHIPSEQ_REPORT(report_records)", foundation)
        self.assertIn("'union', 'intersection', 'replicate_support', 'idr'", foundation)
        self.assertIn("DIFFERENTIAL_BINDING(\n                                CONSENSUS_IDR.out.artifacts", foundation)
        self.assertIn("annotation_sources = CONSENSUS_IDR.out.artifacts", foundation)
        self.assertNotIn("nextflow run", foundation.lower())
        self.assertIn("run_stage full", harness)
        self.assertNotIn("run_stage differential_binding", harness)
        self.assertNotIn("submit_helper hf-chip-prepare", harness)
        self.assertIn("HELIXFORGE_CHIPSEQ_CONSENSUS_METHOD", harness)
        self.assertIn('if [[ "$mode" == "recovery-driver" ]]', harness)
        self.assertIn('resume_args=(-resume)', harness)
        self.assertIn('"${resume_args[@]}"', harness)
        self.assertIn("HELIXFORGE_IDR_PREFIX", harness)
        self.assertIn('ln -sfn "${idr_prefix}/bin/idr" "$compat_bin/idr"', harness)
        self.assertIn('test -e "$repo_root/.git"', harness)
        self.assertIn('--chipseq_consensus_method "$consensus_method"', harness)
        self.assertIn("--chipseq_idr_threshold 0.05", harness)
        self.assertIn("--chipseq_effective_genome_size 30000", harness)


if __name__ == "__main__":
    unittest.main()
