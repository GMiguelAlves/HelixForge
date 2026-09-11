"""Slurm UI contracts. Tests never create real SSH connections or Slurm jobs."""

import http.client
import importlib.util
import json
from pathlib import Path
import subprocess
import threading
import unittest
from unittest.mock import patch
try:
    from .test_submission_documents import base_plan
except ImportError:  # Direct discovery with tests/slurm_ui as the top level.
    from test_submission_documents import base_plan


SPEC = importlib.util.spec_from_file_location("slurm_monitor", Path(__file__).resolve().parents[2] / "ui/slurm/server.py")
monitor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(monitor)
CONFIG = {"host": "example-cluster", "user": "", "port": "", "control_path": ""}


def submission():
    return {"name": "Analysis 01", "workflow": "rnaseq", "runtime": "slurm",
            "repo": "/home/researcher/HelixForge", "config": "/home/researcher/run.config",
            "launch": "/scratch/my_user/run", "output": "/scratch/my_user/run/results", "work": "/scratch/my_user/run/work",
            "memory": "4", "hours": "12", "partition": "general", "account": ""}


def queue_output():
    records = [
        ["123", "nf-task | <script>alert(1)</script>", "RUNNING", "3:05", "1:00:00", "1", "4", "8Gn", "compute", "node01", "2026-09-01T10:00:00", "2026-09-01T10:01:00"],
        ["124_3", "array task", "PENDING", "0:00", "2:00:00", "1", "2", "2Gc", "compute", "(Resources)", "2026-09-01T10:05:00", "N/A"],
    ]
    return "Welcome banner\n" + monitor.MARKER + "researcher\n" + "\n".join(monitor.SEPARATOR.join(row) for row in records) + "\n"


class ConnectionTests(unittest.TestCase):
    def test_ssh_alias_port_user_and_shared_socket_are_separate_arguments(self):
        config = monitor.connection_config({"host": "localhost", "port": "02222", "user": "researcher", "control_path": "/tmp/ssh socket"})
        args = monitor.ssh_arguments(config)
        self.assertEqual(args[args.index("-p") + 1], "2222")
        self.assertEqual(args[args.index("-l") + 1], "researcher")
        self.assertEqual(args[args.index("-S") + 1], "/tmp/ssh socket")
        self.assertEqual(args[-2], "localhost")
        self.assertIn("BatchMode=yes", args)
        self.assertIn("StrictHostKeyChecking=yes", args)
        self.assertIn("ControlMaster=no", args)
        self.assertIn('id -un', args[-1])
        self.assertIn('--user=', args[-1])
        self.assertNotIn("researcher", args[-1])

    def test_config_rejects_options_commands_and_invalid_ports(self):
        invalid = [{"host": "-oProxyCommand=evil"}, {"host": "host;touch /tmp/x"},
                   {"host": "$(command)"}, {"host": "user@host"}, {"host": "fe80::1%$(command)"},
                   {"host": "host", "user": "user;evil"}, {"host": "host", "port": "0"},
                   {"host": "host", "port": "65536"}, {"host": "host", "port": 22},
                   {"host": "host", "command": "id"}, {"host": "host", "control_path": "relative"},
                   {"host": "host", "control_path": "/tmp/%h"}, [], None]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(monitor.MonitorError):
                monitor.connection_config(value)

    def test_ipv6_and_ssh_config_defaults(self):
        self.assertEqual(monitor.connection_config({"host": "::1"})["host"], "::1")
        args = monitor.ssh_arguments(CONFIG)
        self.assertNotIn("-p", args)
        self.assertNotIn("-l", args)


class QueueTests(unittest.TestCase):
    def test_parser_handles_banner_arrays_and_names_with_pipes(self):
        user, jobs = monitor.parse_queue(queue_output())
        self.assertEqual(user, "researcher")
        self.assertEqual(len(jobs), 2)
        self.assertEqual(jobs[1]["id"], "124_3")
        self.assertIn("| <script>", jobs[0]["name"])
        self.assertEqual(jobs[1]["reason"], "(Resources)")

    def test_empty_queue_is_distinct_from_invalid_output(self):
        self.assertEqual(monitor.parse_queue(monitor.MARKER + "researcher\n"), ("researcher", []))
        for output in ("", "squeue not found", monitor.MARKER + "researcher\nbad row", monitor.MARKER + "\n"):
            with self.subTest(output=output), self.assertRaises(monitor.MonitorError):
                monitor.parse_queue(output)

    @patch.object(monitor.subprocess, "run")
    def test_real_adapter_uses_timeout_and_no_local_shell(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, queue_output(), "")
        result = monitor.query_jobs(CONFIG)
        self.assertEqual(result["user"], "researcher")
        self.assertEqual(len(result["jobs"]), 2)
        self.assertEqual(run.call_args.kwargs["timeout"], 25)
        self.assertFalse(run.call_args.kwargs.get("shell", False))
        self.assertEqual(run.call_args.kwargs["stdin"], subprocess.DEVNULL)

    @patch.object(monitor.subprocess, "run")
    def test_failures_never_look_like_successful_empty_queue(self, run):
        for error, message in (("Permission denied", "autenticação"),
                               ("Host key verification failed", "identidade"),
                               ("HF_SQUEUE_MISSING", "PATH"),
                               ("Connection refused", "recusada")):
            run.return_value = subprocess.CompletedProcess([], 255, "", error)
            with self.subTest(error=error), self.assertRaisesRegex(monitor.MonitorError, message):
                monitor.query_jobs(CONFIG)
        run.side_effect = subprocess.TimeoutExpired("ssh", 25)
        with self.assertRaises(monitor.MonitorError) as raised:
            monitor.query_jobs(CONFIG)
        self.assertEqual(raised.exception.status, 504)

    def test_success_and_error_cache_limit_repeated_queries(self):
        now = [0]
        calls = []
        def query(config):
            calls.append(config)
            if config["host"] == "offline":
                raise monitor.MonitorError("offline")
            return {"user": "researcher", "jobs": []}
        cache = monitor.QueueMonitor(query, lambda: now[0])
        cache.get(CONFIG)
        cache.get(CONFIG)
        self.assertEqual(len(calls), 1)
        now[0] = 31
        cache.get(CONFIG)
        self.assertEqual(len(calls), 2)
        for _ in range(2):
            with self.assertRaises(monitor.MonitorError):
                cache.get({**CONFIG, "host": "offline"})
        self.assertEqual(len(calls), 3)

    def test_concurrent_queries_do_not_reach_scheduler(self):
        cache = monitor.QueueMonitor(lambda _: self.fail("Must not query"))
        cache.lock.acquire()
        try:
            with self.assertRaises(monitor.MonitorError) as raised:
                cache.get(CONFIG)
            self.assertEqual(raised.exception.status, 429)
        finally:
            cache.lock.release()


class SubmissionTests(unittest.TestCase):
    def test_draft_validation_rejects_commands_overlaps_and_invalid_resources(self):
        self.assertEqual(monitor.submission_draft(submission())["memory"], "4")
        for changes in ({"partition": "general;id"}, {"output": "/scratch/my_user/run/work/nested"},
                        {"repo": "relative"}, {"config": "/tmp/a\ncommand"}, {"memory": "1.5"},
                        {"runtime": "local"}, {"extra": "field"}):
            value = {**submission(), **changes}
            with self.subTest(changes=changes), self.assertRaises(monitor.MonitorError):
                monitor.submission_draft(value)

    @patch.object(monitor.subprocess, "run")
    def test_remote_adapter_uses_fixed_python_and_structured_stdin(self, run):
        response = {"ok": True, "user": "researcher", "command": "sbatch --parsable ...",
                    "directory": "/scratch/my_user/run/results", "launch": "/scratch/my_user/run"}
        run.return_value = subprocess.CompletedProcess([], 0, "HELIXFORGE_SUBMISSION_V1:" + json.dumps(response) + "\n", "")
        result = monitor.remote_submission(CONFIG, submission(), "prepare")
        self.assertEqual(result["user"], "researcher")
        self.assertFalse(run.call_args.kwargs.get("shell", False))
        self.assertEqual(json.loads(run.call_args.kwargs["input"])["draft"]["partition"], "general")
        self.assertNotIn("/scratch/my_user/run/results", run.call_args.args[0][-1])

    @patch.object(monitor.subprocess, "run", side_effect=subprocess.TimeoutExpired("ssh", 40))
    def test_submit_timeout_is_reported_as_uncertain(self, _run):
        with self.assertRaises(monitor.MonitorError) as raised:
            monitor.remote_submission(CONFIG, submission(), "submit")
        self.assertEqual(raised.exception.code, "uncertain")

    @patch.object(monitor.subprocess, "run")
    def test_remote_response_must_match_reviewed_paths(self, run):
        response = {"ok": True, "user": "researcher", "command": "sbatch --parsable ...",
                    "directory": "/different/results", "launch": "/scratch/my_user/run"}
        run.return_value = subprocess.CompletedProcess([], 0, "HELIXFORGE_SUBMISSION_V1:" + json.dumps(response), "")
        with self.assertRaises(monitor.MonitorError) as raised:
            monitor.remote_submission(CONFIG, submission(), "prepare")
        self.assertEqual(raised.exception.code, "response")

    @patch.object(monitor.subprocess, "run")
    def test_preparation_adapter_keeps_documents_in_stdin(self, run):
        response = {"state":"ready"}
        run.return_value = subprocess.CompletedProcess([], 0, "HELIXFORGE_PREPARATION_V1:" + json.dumps(response), "")
        request = {"action":"preflight", "documents":[{"path":"/home/project/run.config", "content":"secret"}]}
        self.assertEqual(monitor.remote_preparation(CONFIG, request), response)
        self.assertEqual(json.loads(run.call_args.kwargs["input"]), request)
        self.assertNotIn("secret", run.call_args.args[0][-1])


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        def query(_config):
            user, jobs = monitor.parse_queue(queue_output())
            return {"user": user, "jobs": jobs, "checked_at": "2026-09-01T12:00:00+00:00"}
        cls.server = monitor.MonitorServer(("127.0.0.1", 0), monitor.QueueMonitor(query))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            conn.request(method, path, body=body, headers=headers or {})
            response = conn.getresponse()
            return response.status, response.getheaders(), response.read()
        finally:
            conn.close()

    def test_ui_and_api_round_trip(self):
        status, headers, body = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(self.server.token.encode(), body)
        self.assertNotIn(b"__SESSION_TOKEN__", body)
        self.assertIn("frame-ancestors 'none'", dict(headers)["Content-Security-Policy"])
        self.assertEqual(dict(headers)["X-Frame-Options"], "DENY")
        self.assertEqual(dict(headers)["Cross-Origin-Resource-Policy"], "same-origin")
        status, _, body = self.request("POST", "/api/jobs", json.dumps(CONFIG),
            {"Content-Type": "application/json", "X-HelixForge-Token": self.server.token})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["jobs"][1]["id"], "124_3")

    def test_cross_origin_and_untrusted_host_cannot_query_ssh(self):
        for headers in ({}, {"X-HelixForge-Token": self.server.token, "Origin": "https://untrusted.example"},
                        {"X-HelixForge-Token": self.server.token, "Host": "untrusted.example"}):
            status, _, _ = self.request("POST", "/api/jobs", json.dumps(CONFIG), headers)
            self.assertEqual(status, 403)
        self.assertEqual(self.request("GET", "/", headers={"Host": "untrusted.example"})[0], 403)

    def test_unknown_paths_and_bad_json_are_rejected(self):
        self.assertEqual(self.request("GET", "/../../server.py")[0], 404)
        self.assertEqual(self.request("POST", "/api/jobs", "not json", {
            "X-HelixForge-Token": self.server.token, "Content-Type": "application/json"})[0], 400)

    def test_execution_endpoint_requires_session_and_returns_inspection(self):
        payload = json.dumps({"connection": CONFIG, "directory": "/scratch/my_user/run"})
        self.assertEqual(self.request("POST", "/api/execution", payload)[0], 403)
        with patch.object(self.server.executions, "query", return_value={"tasks": [], "trace_found": False}):
            status, _, body = self.request("POST", "/api/execution", payload, {
                "X-HelixForge-Token": self.server.token, "Content-Type": "application/json"})
        self.assertEqual(status, 200)
        self.assertFalse(json.loads(body)["trace_found"])
        self.assertEqual(self.request("GET", "/executions.js")[0], 200)

    def test_execution_error_exposes_machine_readable_availability(self):
        payload = json.dumps({"connection": CONFIG, "directory": "/output/run"})
        headers = {"X-HelixForge-Token": self.server.token, "Content-Type": "application/json"}
        with patch.object(self.server.executions, "query", side_effect=monitor.MonitorError("Arquivo ausente.", 400, "missing")):
            status, _, body = self.request("POST", "/api/execution", payload, headers)
        self.assertEqual(status, 400)
        self.assertEqual(json.loads(body), {"error": "Arquivo ausente.", "code": "missing"})
        self.assertEqual(self.request("GET", "/execution-state.js")[0], 200)

    def test_profile_validation_never_connects_to_remote(self):
        headers = {"X-HelixForge-Token": self.server.token, "Content-Type": "application/json"}
        with patch.object(monitor.subprocess, "run", side_effect=AssertionError("Must not connect")):
            status, _, body = self.request("POST", "/api/connection", json.dumps({**CONFIG, "port": "022"}), headers)
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body)["connection"]["port"], "22")
            self.assertEqual(self.request("POST", "/api/connection", json.dumps({**CONFIG, "host": "-oProxyCommand=bad"}), headers)[0], 400)
            self.assertEqual(self.request("POST", "/api/connection", json.dumps(CONFIG))[0], 403)

    def test_submission_requires_review_and_consumes_token_once(self):
        headers = {"X-HelixForge-Token": self.server.token, "Content-Type": "application/json"}
        prepared = {"ok": True, "user": "researcher", "command": "sbatch --parsable ...",
                    "directory": "/scratch/my_user/run/results", "launch": "/scratch/my_user/run"}
        submitted = {**prepared, "job_id": "12345"}
        self.server.submissions.clear()
        with patch.object(monitor, "remote_submission", side_effect=[prepared, submitted]) as remote:
            status, _, body = self.request("POST", "/api/submission/prepare",
                json.dumps({"connection": CONFIG, "draft": submission()}), headers)
            self.assertEqual(status, 200)
            token = json.loads(body)["review_token"]
            status, _, body = self.request("POST", "/api/submission/submit", json.dumps({"review_token": token}), headers)
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body)["job_id"], "12345")
            self.assertEqual(self.request("POST", "/api/submission/submit", json.dumps({"review_token": token}), headers)[0], 409)
            self.assertEqual([call.args[2] for call in remote.call_args_list], ["prepare", "submit"])

    def test_invalid_submission_is_rejected_before_ssh(self):
        headers = {"X-HelixForge-Token": self.server.token, "Content-Type": "application/json"}
        with patch.object(monitor, "remote_submission", side_effect=AssertionError("Must not connect")):
            status, _, body = self.request("POST", "/api/submission/prepare",
                json.dumps({"connection": CONFIG, "draft": {**submission(), "partition": "x;id"}}), headers)
        self.assertEqual(status, 400)
        self.assertEqual(json.loads(body)["code"], "invalid")

    def test_document_review_must_precede_atomic_write(self):
        headers = {"X-HelixForge-Token": self.server.token, "Content-Type": "application/json"}
        preflight = {"state":"ready", "clone":{"ref":"master", "commit":"a" * 40, "dirty":False},
                     "inputs":10, "documents":5, "java":"21", "nextflow":"25.10.7", "sbatch":True}
        written = {"state":"written", "project_root":"/home/researcher/projects/analysis-01", "documents":["/home/researcher/projects/analysis-01/run.config"]}
        self.server.preparations.clear()
        with patch.object(monitor, "remote_preparation", side_effect=[preflight, written]) as remote:
            status, _, body = self.request("POST", "/api/preparation/review", json.dumps({"connection":CONFIG, "plan":base_plan()}), headers)
            self.assertEqual(status, 200)
            review = json.loads(body)
            self.assertGreaterEqual(len(review["documents"]), 5)
            token = review["review_token"]
            status, _, body = self.request("POST", "/api/preparation/write", json.dumps({"review_token":token}), headers)
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body)["draft"]["config"], "/home/researcher/projects/analysis-01/run.config")
            self.assertEqual(self.request("POST", "/api/preparation/write", json.dumps({"review_token":token}), headers)[0], 409)
            self.assertEqual([call.args[1]["action"] for call in remote.call_args_list], ["preflight", "write"])

    def test_clone_creation_requires_separate_review_token(self):
        headers = {"X-HelixForge-Token": self.server.token, "Content-Type": "application/json"}
        clone = {"mode":"new", "path":"/home/researcher/HelixForge-v1", "repository":"https://github.com/GMiguelAlves/HelixForge.git", "ref":"v1.0.0"}
        ready = {"state":"ready_to_clone", "path":clone["path"], "repository":clone["repository"], "ref":clone["ref"], "commit":"a" * 40, "command":"git clone ..."}
        created = {"state":"available", "path":clone["path"], "commit":"b" * 40, "ref":"v1.0.0", "dirty":False}
        self.server.preparations.clear()
        with patch.object(monitor, "remote_preparation", side_effect=[ready, created]) as remote:
            status, _, body = self.request("POST", "/api/clone/review", json.dumps({"connection":CONFIG, "clone":clone}), headers)
            self.assertEqual(status, 200); token = json.loads(body)["review_token"]
            self.assertEqual(self.request("POST", "/api/clone/create", json.dumps({"review_token":token}), headers)[0], 200)
            self.assertEqual(self.request("POST", "/api/clone/create", json.dumps({"review_token":token}), headers)[0], 409)
            self.assertEqual(remote.call_args_list[1].args[1]["clone"]["ref"], "a" * 40)

    def test_invalid_plan_never_reaches_remote_preparation(self):
        headers = {"X-HelixForge-Token": self.server.token, "Content-Type": "application/json"}
        plan = base_plan(); plan["storage"]["work"] = "../../bad"
        with patch.object(monitor, "remote_preparation", side_effect=AssertionError("Must not connect")):
            status, _, body = self.request("POST", "/api/preparation/review", json.dumps({"connection":CONFIG, "plan":plan}), headers)
        self.assertEqual(status, 400)
        self.assertTrue(json.loads(body)["code"].startswith("invalid:"))


if __name__ == "__main__":
    unittest.main()
