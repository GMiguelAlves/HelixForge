"""Submission UI tests never invoke sbatch, Nextflow, or SSH."""
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import unittest


@unittest.skipUnless(shutil.which("node"), "Node is needed for command builder tests")
class NewExecutionTests(unittest.TestCase):
    def build(self, **changes):
        draft = dict(name="Analysis 01", host="cluster", workflow="rnaseq", runtime="slurm",
                     repo="/home/researcher/HelixForge", config="/home/researcher/run.config",
                     launch="/scratch/my_user/run", output="/scratch/my_user/run/results", work="/scratch/my_user/run/work",
                     memory="4", hours="12", partition="general", account="")
        draft.update(changes)
        source = Path(__file__).resolve().parents[2] / "ui/slurm/static/new-execution.js"
        code = "const {buildExecutionCommand}=require(process.argv[1]);try{console.log(JSON.stringify({command:buildExecutionCommand(JSON.parse(process.argv[2]))}));}catch(e){console.log(JSON.stringify({error:e.message}));}"
        result = subprocess.run(["node", "-e", code, str(source), json.dumps(draft)], capture_output=True, text=True, check=True, timeout=10)
        return json.loads(result.stdout)

    def test_command_submits_coordinator_and_preserves_workflow(self):
        command = self.build()["command"]
        argv = shlex.split(command.replace("\\\n", ""))
        self.assertEqual(argv[0], "sbatch")
        self.assertEqual(argv[argv.index("--cpus-per-task") + 1], "1")
        self.assertEqual(argv[argv.index("--chdir") + 1], "/scratch/my_user/run")
        inner = shlex.split(argv[argv.index("--wrap") + 1])
        self.assertEqual(inner[:3], ["exec", "nextflow", "run"])
        self.assertEqual(inner[inner.index("--workflow") + 1], "rnaseq")
        self.assertNotIn("-resume", inner)

    def test_shell_metacharacters_remain_literal_path_arguments(self):
        path = "/home/researcher/config '$(touch BAD);`.config"
        argv = shlex.split(self.build(config=path)["command"].replace("\\\n", ""))
        inner = shlex.split(argv[argv.index("--wrap") + 1])
        self.assertEqual(inner[inner.index("-c") + 1], path)

    def test_invalid_or_overlapping_directories_are_rejected(self):
        for changes in ({"output": "/scratch/my_user/run/work/nested"}, {"work": "/scratch"}, {"launch": "relative"},
                        {"output": "/scratch/my_user/../results"}, {"config": "/tmp/file\ncommand"}, {"launch": "/scratch/my_user/%j"}):
            with self.subTest(changes=changes):
                self.assertIn("error", self.build(**changes))

    def test_resources_and_controlled_options_are_validated(self):
        for changes in ({"hours": "0"}, {"memory": "1.5"}, {"partition": "general;bad"},
                        {"workflow": "bad"}, {"runtime": "local"}, {"host": ""}):
            with self.subTest(changes=changes):
                self.assertIn("error", self.build(**changes))

    def test_ui_uses_review_then_submit_endpoints(self):
        source = (Path(__file__).resolve().parents[2] / "ui/slurm/static/new-execution.js").read_text(encoding="utf-8")
        for endpoint in ("/api/clone/review", "/api/clone/create", "/api/preparation/review", "/api/preparation/write", "/api/submission/prepare", "/api/submission/submit"):
            self.assertIn(endpoint, source)
        self.assertIn("registerSubmittedExecution", source)
        self.assertNotIn("localStorage", source)
