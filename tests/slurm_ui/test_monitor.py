"""Read-only monitor contracts. No real SSH connections or Slurm jobs."""

import http.client
import importlib.util
import json
from pathlib import Path
import subprocess
import threading
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location("slurm_monitor", Path(__file__).resolve().parents[2] / "ui/slurm/server.py")
monitor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(monitor)
CONFIG = {"host": "example-cluster", "user": "", "port": "", "control_path": ""}


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


if __name__ == "__main__":
    unittest.main()
