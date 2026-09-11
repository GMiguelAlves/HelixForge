import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("remote_prepare", ROOT / "ui/slurm/remote_prepare.py")
remote = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(remote)


@unittest.skipUnless(hasattr(os, "getuid"), "Remote preparation runs on Linux")
class AtomicWriteTests(unittest.TestCase):
    def test_new_clone_review_pins_the_resolved_commit(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "clone"
            commit = "a" * 40
            result = remote.subprocess.CompletedProcess([], 0, commit + "\trefs/heads/master\n", "")
            clone = {"mode":"new", "path":str(target), "repository":"https://github.com/GMiguelAlves/HelixForge.git", "ref":"master"}
            with patch.object(remote.shutil, "which", return_value="/usr/bin/git"), patch.object(remote, "run", return_value=result):
                inspected = remote.inspect_clone(clone)
            self.assertEqual(inspected["commit"], commit)
            self.assertIn("checkout --detach " + commit, inspected["command"])

    def test_integrative_manifest_contract_is_checked_before_writing(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            manifests = []
            for assay in ("rna", "chip"):
                folder = base / assay; folder.mkdir(); (folder / "integration_artifacts").mkdir()
                manifest = folder / f"{assay}.json"
                manifest.write_text(json.dumps({"schema_version":"1.0", "type":"wrong", "reference":{}, "artifacts":[]}))
                manifests.append(str(manifest))
            request = {"clone":{}, "inputs":manifests, "documents":[], "project_root":str(base / "project"),
                       "integration":{"rna_manifest":manifests[0], "chip_manifest":manifests[1]}}
            with patch.object(remote, "inspect_clone", return_value={"state":"available"}), self.assertRaises(SystemExit):
                remote.preflight(request)

    def test_preflight_validates_storage_and_partition(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary); clone = base / "clone"; clone.mkdir()
            for name in ("main.nf", "nextflow.config"): (clone / name).write_text("ok")
            (clone / ".git").mkdir(); launch = base / "launch"; launch.mkdir()
            request = {"clone":{"mode":"existing", "path":str(clone), "repository":"", "ref":""},
                       "inputs":[], "documents":[], "project_root":str(base / "project"),
                       "storage":{"launch":str(launch), "output":str(base / "output"), "work":str(base / "work")},
                       "runtime":{"profile":"slurm", "partition":"general", "account":""}}
            def command(args, timeout=20):
                if args[:2] == ["java", "-version"]:
                    return remote.subprocess.CompletedProcess(args, 0, "", 'openjdk version "21.0.4"')
                if args[:2] == ["nextflow", "-version"]:
                    return remote.subprocess.CompletedProcess(args, 0, "nextflow version 25.10.7", "")
                return remote.subprocess.CompletedProcess(args, 0, "ok\n", "")
            with patch.object(remote.os, "getuid", return_value=clone.stat().st_uid), patch.object(remote.shutil, "which", return_value="/bin/tool"), patch.object(remote, "run", side_effect=command):
                result = remote.preflight(request)
            self.assertEqual(result["partition"], "general")
            self.assertEqual(result["storage"], "destinos novos e graváveis")

    def test_documents_are_staged_then_published_as_one_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "analysis"
            documents = [{"path":str(root / "run.config"), "relative_path":"run.config", "content":"params {}\n"},
                         {"path":str(root / "config/metadata.tsv"), "relative_path":"config/metadata.tsv", "content":"sample_id\nA\n"}]
            request = {"project_root":str(root), "documents":documents}
            with patch.object(remote, "preflight", return_value={"state":"ready"}):
                result = remote.write_documents(request)
            self.assertEqual(result["state"], "written")
            self.assertEqual((root / "run.config").read_text(), "params {}\n")
            self.assertEqual((root / "config/metadata.tsv").read_text(), "sample_id\nA\n")
            self.assertFalse(list(Path(temporary).glob(".helixforge-preparation-*")))

    def test_invalid_second_document_cleans_staging_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "analysis"
            documents = [{"path":str(root / "run.config"), "relative_path":"run.config", "content":"ok"},
                         {"path":str(root / "bad"), "relative_path":"../bad", "content":"bad"}]
            with patch.object(remote, "preflight", return_value={"state":"ready"}), self.assertRaises(SystemExit):
                remote.write_documents({"project_root":str(root), "documents":documents})
            self.assertFalse(root.exists())
            self.assertFalse(list(Path(temporary).glob(".helixforge-preparation-*")))

    def test_clone_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "target"; target.mkdir()
            link = Path(temporary) / "clone"; link.symlink_to(target, target_is_directory=True)
            with self.assertRaises(SystemExit):
                remote.inspect_clone({"mode":"existing", "path":str(link), "repository":"", "ref":""})


if __name__ == "__main__":
    unittest.main()
