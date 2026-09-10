"""Synthetic result fixtures only; no infrastructure or biological data."""
import os
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from test_executions import probe
from test_monitor import CONFIG, monitor


class ResultAPITests(unittest.TestCase):
    def test_invalid_file_request_never_connects(self):
        for path in ('../secret', '/secret', 'a/../b', 'a//b', 'a\\b', 'a\n'):
            with patch.object(monitor.subprocess, 'run', side_effect=AssertionError('Must not connect')):
                with self.assertRaises(monitor.MonitorError):
                    monitor.query_execution({'connection': CONFIG, 'directory': '/output',
                                             'file': {'path': path, 'offset': 0, 'preview': False}})
        for offset in (-1, True, '0', 2**53):
            with self.assertRaises(ValueError):
                probe.validate_file({'path': 'x.log', 'offset': offset, 'preview': False})

    def test_html_is_static_before_it_reaches_browser(self):
        content = '<meta http-equiv="refresh" content="0;url=https://example.invalid"><script>alert(1)</script><iframe src="https://example.invalid"></iframe><svg onload="alert(1)"></svg><a href="https://example.invalid">link</a><p onclick="alert(1)">safe</p><img src="https://example.invalid"><form action="/api/jobs"><input></form>'
        safe = probe.static_report(content)
        self.assertEqual(safe, 'link<p>safe</p>')
        self.assertIn('&lt;img', probe.static_report('<p>&lt;img src=x onerror=evil&gt;</p>'))


@unittest.skipUnless(hasattr(os, 'getuid'), 'Remote probe runs on Linux')
class ResultProbeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def read(self, path, offset=0, preview=False):
        return probe.read_file(self.root, {'path': path, 'offset': offset, 'preview': preview})

    def test_audit_layout_keeps_failed_attempts_separate(self):
        execution = self.root / 'execution'
        execution.mkdir()
        (execution / 'trace.tsv').write_text('name\tstatus\tnative_id\nmain\tCOMPLETED\t1\n')
        failed = self.root / 'failed_attempts'
        failed.mkdir()
        (failed / 'trace.tsv').write_text('name\tstatus\tnative_id\nold\tFAILED\t2\n')
        (execution / 'nextflow.log').write_text('Workflow completed\n')
        data = probe.inspect(self.root)
        self.assertEqual(data['trace_path'], 'execution/trace.tsv')
        self.assertEqual([t['name'] for t in data['tasks']], ['main'])
        self.assertIn('failed_attempts/trace.tsv', data['artifacts'])

    def test_large_sparse_table_reads_only_requested_window(self):
        path = self.root / 'large.tsv'
        with path.open('wb') as handle:
            handle.write(b'gene\tvalue\n')
            handle.seek(300 * 1024 * 1024)
            handle.write(b'last\t42\n')
        first = self.read('large.tsv')
        self.assertEqual(len(first['content']), 65536)
        self.assertTrue(first['truncated'])
        tail = self.read('large.tsv', path.stat().st_size - 8)
        self.assertEqual(tail['content'], 'last\t42\n')
        self.assertFalse(tail['truncated'])
        with self.assertRaises(ValueError):
            self.read('large.tsv', preview=True)

    def test_preview_limits_and_empty_logs(self):
        (self.root / 'empty.log').write_text('')
        self.assertEqual(self.read('empty.log')['content'], '')
        (self.root / 'report.html').write_text('<h1>Report</h1><script>bad()</script>')
        self.assertEqual(self.read('report.html', preview=True)['content'], '<h1>Report</h1>')
        (self.root / 'report.html').write_bytes(b'x' * (probe.PREVIEW_LIMIT + 1))
        with self.assertRaises(ValueError):
            self.read('report.html', preview=True)

    def test_manifest_status_is_attributed_and_partial_json_does_not_hide_results(self):
        (self.root / 'run_manifest.json').write_text('{"status":"complete_empty"}')
        (self.root / 'report_manifest.json').write_text('{"status":')
        data = probe.inspect(self.root)
        self.assertEqual(data['declarations'], [{'path': 'run_manifest.json', 'status': 'complete_empty'}])
        self.assertIn('report_manifest.json', data['artifacts'])
        self.assertNotIn('status', data)

    def test_symlinks_special_files_and_unlisted_files(self):
        outside = self.root / 'secret'
        outside.write_text('private')
        (self.root / 'escape.log').symlink_to(outside)
        os.mkfifo(self.root / 'pipe.log')
        for path in ('escape.log', 'pipe.log', 'secret'):
            with self.assertRaises(ValueError):
                self.read(path)
        (self.root / 'integration').symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(OSError):
            with probe.open_result(self.root, 'integration/secret'):
                self.fail('Symlink directory must not open')

    def test_inventory_limit_is_explicit(self):
        for i in range(1001):
            (self.root / f'{i}.json').write_text('{}')
        data = probe.inspect(self.root)
        self.assertTrue(data['artifacts_truncated'])
        self.assertEqual(len(data['artifacts']), 1000)
