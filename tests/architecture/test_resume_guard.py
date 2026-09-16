import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / "bin" / "helixforge-resume-guard"


class ResumeGuardTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.work = self.root / "work"
        self.work.mkdir()
        self.task = self.work / "aa" / "task"
        self.task.mkdir(parents=True)
        (self.task / ".exitcode").write_text("0\n", encoding="utf-8")
        self.rows = self.root / "log.tsv"
        self.rows.write_text(
            f"aa/bbccdd\tFLOW:STEP (sample)\tCOMPLETED\t0\t{self.task}\n",
            encoding="utf-8",
        )
        self.receipt = self.root / "resume-receipt.json"

    def tearDown(self):
        self.temporary.cleanup()

    def run_guard(self, mode, rows=None):
        return subprocess.run(
            [
                sys.executable,
                str(GUARD),
                mode,
                "--run-name",
                "frozen-run",
                "--receipt",
                str(self.receipt),
                "--work-dir",
                str(self.work),
                "--log-tsv",
                str(rows or self.rows),
            ],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_capture_then_check(self):
        captured = self.run_guard("capture")
        self.assertEqual(captured.returncode, 0, captured.stderr)
        checked = self.run_guard("check")
        self.assertEqual(checked.returncode, 0, checked.stderr)
        payload = json.loads(self.receipt.read_text(encoding="utf-8"))
        self.assertEqual(payload["task_count"], 1)
        self.assertEqual(payload["tasks"][0]["workdir"], "aa/task")
        self.assertNotIn(str(self.root), self.receipt.read_text(encoding="utf-8"))

    def test_empty_cache_fails_closed(self):
        empty = self.root / "empty.tsv"
        empty.write_text("", encoding="utf-8")
        result = self.run_guard("capture", empty)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no recoverable entries", result.stderr)
        self.assertFalse(self.receipt.exists())

    def test_failed_rows_are_excluded_from_partial_run_receipt(self):
        failed = self.root / "failed.tsv"
        failed.write_text(
            self.rows.read_text(encoding="utf-8")
            + "ff/failed\tFLOW:FAILED (sample)\tFAILED\t1\t\n",
            encoding="utf-8",
        )
        result = self.run_guard("capture", failed)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ignored non-recoverable task records: 1", result.stderr)
        payload = json.loads(self.receipt.read_text(encoding="utf-8"))
        self.assertEqual(payload["task_count"], 1)

    def test_missing_workdir_fails_closed(self):
        self.task.rename(self.root / "removed-task")
        result = self.run_guard("capture")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("task workdir does not exist", result.stderr)

    def test_changed_live_cache_is_rejected(self):
        self.assertEqual(self.run_guard("capture").returncode, 0)
        changed_task = self.work / "bb" / "task"
        changed_task.mkdir(parents=True)
        (changed_task / ".exitcode").write_text("0\n", encoding="utf-8")
        changed = self.root / "changed.tsv"
        changed.write_text(
            self.rows.read_text(encoding="utf-8")
            + f"bb/ccddee\tFLOW:OTHER (sample)\tCOMPLETED\t0\t{changed_task}\n",
            encoding="utf-8",
        )
        result = self.run_guard("check", changed)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("count differs", result.stderr)


if __name__ == "__main__":
    unittest.main()
