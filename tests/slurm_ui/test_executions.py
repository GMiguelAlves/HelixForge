import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from test_monitor import CONFIG, monitor

SPEC = importlib.util.spec_from_file_location("execution_probe", Path(monitor.__file__).with_name("probe.py"))
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


class ExecutionAPITests(unittest.TestCase):
    def test_directory_is_stdin_data_never_shell_code(self):
        directory = "/scratch/my run/$(touch danger); 'quoted'"
        result = subprocess.CompletedProcess([], 0, 'banner\nHELIXFORGE_EXECUTION_V1:{"tasks":[],"directory":"/scratch/run"}\n', '')
        with patch.object(monitor.subprocess, "run", return_value=result) as call:
            data = monitor.query_execution({"connection": CONFIG, "directory": directory})
        args, kwargs = call.call_args
        self.assertNotIn(directory, args[0][-1])
        self.assertEqual(json.loads(kwargs["input"])["directory"], directory)
        self.assertEqual(kwargs["timeout"], 25)
        self.assertNotIn("shell", kwargs)
        self.assertIn("checked_at", data)

    def test_bad_paths_and_remote_failures_are_not_empty_success(self):
        for directory in ("relative", "~", "/bad\npath", 123):
            with self.assertRaises(monitor.MonitorError):
                monitor.query_execution({"connection": CONFIG, "directory": directory})
        for output in ('', 'HELIXFORGE_EXECUTION_V1:{"error":"sem permissão"}', 'HELIXFORGE_EXECUTION_V1:broken'):
            with patch.object(monitor.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, output, '')):
                with self.assertRaises(monitor.MonitorError):
                    monitor.query_execution({"connection": CONFIG, "directory": "/scratch/run"})


@unittest.skipUnless(hasattr(os, "getuid"), "Remote probe runs on Linux")
class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "pipeline_info").mkdir()
        self.trace = self.root / "pipeline_info/execution_trace.tsv"

    def test_missing_trace_is_not_completed_execution(self):
        data = probe.inspect(self.root)
        self.assertFalse(data["trace_found"])
        self.assertEqual(data["tasks"], [])
        self.assertNotIn("status", data)

    def test_trace_artifacts_and_partial_writer_record(self):
        self.trace.write_text("name\tstatus\tnative_id\tduration\nstep <a>\tFAILED\t123\t2s\nunfinished\tRUN", encoding="utf-8")
        (self.root / "pipeline_info/execution_report.html").write_text("report")
        data = probe.inspect(self.root)
        self.assertEqual(len(data["tasks"]), 1)
        self.assertEqual(data["tasks"][0]["status"], "FAILED")
        self.assertEqual(data["tasks"][0]["name"], "step <a>")
        self.assertEqual(data["artifacts"], ["pipeline_info/execution_report.html"])

    def test_symlink_escape_and_special_file_are_rejected(self):
        with tempfile.NamedTemporaryFile() as other:
            self.trace.symlink_to(other.name)
            with self.assertRaises(ValueError):
                probe.inspect(self.root)
        self.trace.unlink()
        os.mkfifo(self.trace)
        with self.assertRaises(ValueError):
            probe.inspect(self.root)

    def test_foreign_ownership_is_rejected(self):
        with patch.object(probe.os, "getuid", return_value=os.getuid() + 1):
            with self.assertRaises(ValueError):
                probe.inspect(self.root)

    def test_large_or_malformed_trace_is_rejected(self):
        for content in ("x" * (2 * 1024 * 1024 + 1), "unexpected\tcolumns\n", "name\tstatus\tnative_id\na\tFAILED\n"):
            self.trace.write_text(content)
            with self.assertRaises(ValueError):
                probe.inspect(self.root)
