"""Synthetic result fixtures only; no infrastructure or biological data."""
import os
import base64
import json
import shutil
import subprocess
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

    def test_missing_permission_and_partial_are_distinct(self):
        for failure, code in ((FileNotFoundError(), 'missing'), (PermissionError(), 'permission'),
                              (ValueError('incomplete'), 'partial')):
            with patch.object(probe, 'inspect', side_effect=failure):
                result = probe.handle_request({'directory': '/output'})
            self.assertEqual(result['code'], code)
            self.assertIn('error', result)


@unittest.skipUnless(shutil.which('node'), 'Node is needed for snapshot state tests')
class SnapshotStateTests(unittest.TestCase):
    def node(self, script, *values):
        source = Path(__file__).resolve().parents[2] / 'ui/slurm/static/execution-state.js'
        result = subprocess.run(['node', '-e', script, str(source), *(json.dumps(value) for value in values)],
                                capture_output=True, text=True, check=True, timeout=10)
        return json.loads(result.stdout)

    def run_state(self, previous, current=None, reason=None):
        script = "const s=require(process.argv[1]),p=JSON.parse(process.argv[2]),c=JSON.parse(process.argv[3]);console.log(JSON.stringify(c.reason?s.preserveExecutionSnapshot(p,c.reason,'2026-09-10T12:00:00Z'):s.executionRegression(p,c.current)))"
        payload = {'reason': reason} if reason else {'current': current}
        return self.node(script, previous, payload)

    def test_missing_trace_artifact_and_changed_identity_are_regressions(self):
        previous = {'fingerprint':'one', 'trace_found':True, 'artifacts':['report.html']}
        self.assertEqual(self.run_state(previous, {'fingerprint':'one', 'trace_found':False, 'artifacts':['report.html']})['code'], 'missing')
        self.assertEqual(self.run_state(previous, {'fingerprint':'one', 'trace_found':True, 'artifacts':[]})['code'], 'missing')
        self.assertEqual(self.run_state(previous, {'fingerprint':'two', 'trace_found':True, 'artifacts':['report.html']})['code'], 'identity')
        self.assertIsNone(self.run_state(previous, previous))

    def test_partial_trace_and_disappearing_detailed_artifact_preserve_snapshot(self):
        previous = {'trace_found':True, 'artifacts':['report.html'], 'artifact_details':[{'path':'report.html'}],
                    'health':{'trace':{'state':'available'}}}
        partial = {**previous, 'health':{'trace':{'state':'partial'}}}
        self.assertEqual(self.run_state(previous, partial)['code'], 'partial')
        missing = {**previous, 'artifact_details':[], 'health':{'trace':{'state':'available'}}}
        self.assertEqual(self.run_state(previous, missing)['code'], 'missing')

    def test_stale_snapshot_keeps_last_valid_data_and_bounded_history(self):
        run = {'data':{'tasks':[{}], 'artifacts':['report.html'], 'health':{'trace':{'state':'available'}}},
               'history':[{'checked_at':str(i)} for i in range(12)]}
        preserved = self.run_state(run, reason='permission')
        self.assertEqual(preserved['data'], run['data'])
        self.assertEqual(preserved['availability']['state'], 'stale')
        self.assertEqual(preserved['availability']['reason'], 'permission')
        self.assertEqual(len(preserved['history']), 10)

    def test_job_correlation_requires_exact_id_and_same_connection(self):
        script = "const s=require(process.argv[1]);console.log(JSON.stringify(s.findCurrentSlurmJob(...[2,3,4,5].map(i=>JSON.parse(process.argv[i])))))"
        config = {'host':'cluster', 'user':'', 'port':'', 'control_path':''}
        queue = {'jobs':[{'id':'123', 'state':'RUNNING'}, {'id':'123_1', 'state':'PENDING'}]}
        self.assertEqual(self.node(script, {'native_id':'123'}, config, config, queue)['state'], 'RUNNING')
        self.assertIsNone(self.node(script, {'native_id':'12'}, config, config, queue))
        self.assertIsNone(self.node(script, {'native_id':'123'}, config, {**config, 'host':'other'}, queue))

    def test_local_removal_can_be_undone_without_touching_remote_files(self):
        script = "const s=require(process.argv[1]),runs=JSON.parse(process.argv[2]);const x=s.removeExecutionLocally(runs,'one');console.log(JSON.stringify({x,restored:s.restoreExecutionLocally(x.remaining,x.removed)}))"
        result = self.node(script, [{'id':'one'}, {'id':'two'}])
        self.assertEqual(result['x']['removed']['id'], 'one')
        self.assertEqual([run['id'] for run in result['x']['remaining']], ['two'])
        self.assertEqual([run['id'] for run in result['restored']], ['one', 'two'])


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
        archived = next(item for item in data['artifact_details'] if item['path'] == 'failed_attempts/trace.tsv')
        self.assertTrue(archived['archived'])
        self.assertEqual(archived['group'], 'archived')
        self.assertEqual(data['health']['files']['archived'], 1)
        self.assertEqual(data['health']['trace']['state'], 'available')

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

    def test_full_audit_with_removed_workdirs_keeps_archived_results_readable(self):
        for directory in ('traces', 'logs', 'operational', 'final_report', 'idr', 'provenance'):
            (self.root / directory).mkdir()
        trace = self.root / 'traces/full.tsv'
        trace.write_text('task_id\tnative_id\tname\tstatus\tworkdir\n'
                         f'1\t101\tIDR\tCOMPLETED\t{self.root}/removed-work\n')
        artifacts = {
            'logs/full.nextflow.log': 'Workflow completed\n',
            'logs/full.nextflow.log.1': 'Earlier attempt\n',
            'logs/slurm.err': '',
            'operational/full.report.html': '<h1>Execution</h1>',
            'operational/full.timeline.html': '<h1>Timeline</h1>',
            'operational/full.dag.html': '<h1>DAG</h1>',
            'final_report/chipseq_report.html': '<h1>ChIP-seq</h1>',
            'provenance/run_manifest.json': '{"status":"complete"}',
            'idr/peaks.narrowPeak': 'chr1\t0\t100\n',
        }
        for path, content in artifacts.items():
            (self.root / path).write_text(content)
        data = probe.inspect(self.root)
        self.assertEqual(data['trace_path'], 'traces/full.tsv')
        self.assertEqual(data['tasks'][0]['status'], 'COMPLETED')
        self.assertEqual(set(data['artifacts']), set(artifacts))
        for path, content in artifacts.items():
            self.assertEqual(self.read(path)['content'], content)
        selection = {'task_id': '1', 'native_id': '101', 'name': 'IDR', 'file': '.command.out'}
        with self.assertRaises(FileNotFoundError):
            probe.read_log(self.root, selection)
        # The fallback must not replace an explicit primary execution trace.
        (self.root / 'trace.tsv').write_text('name\tstatus\tnative_id\nprimary\tFAILED\t102\n')
        self.assertEqual(probe.inspect(self.root)['tasks'][0]['name'], 'primary')

    def test_preserved_benchmark_groups_and_direct_registration_without_trace(self):
        for group in ('contracts', 'reentry', 'real', 'synthetic'):
            directory = self.root / group
            directory.mkdir()
            (directory / 'acceptance.tsv').write_text('criterion\tstatus\nexample\tPASS\n')
            nested = directory / 'case' / 'evaluation'
            nested.mkdir(parents=True)
            (nested / 'summary.json').write_text('{}')
        data = probe.inspect(self.root)
        self.assertFalse(data['trace_found'])
        self.assertEqual(data['tasks'], [])
        self.assertEqual(len(data['artifacts']), 8)
        for group in ('contracts', 'reentry', 'real', 'synthetic'):
            self.assertIn(f'{group}/acceptance.tsv', data['artifacts'])
            self.assertIn(f'{group}/case/evaluation/summary.json', data['artifacts'])
            self.assertIn('PASS', self.read(f'{group}/acceptance.tsv')['content'])
        direct = probe.inspect(self.root / 'reentry')
        self.assertFalse(direct['trace_found'])
        self.assertIn('acceptance.tsv', direct['artifacts'])
        self.assertNotIn('status', direct)

    def test_benchmark_groups_preserve_catalog_boundaries(self):
        group = self.root / 'synthetic'
        group.mkdir()
        for name in ('work', '.nextflow'):
            directory = group / name
            directory.mkdir()
            (directory / 'private.json').write_text('{}')
        other = self.root / 'unlisted'
        other.mkdir()
        (other / 'private.json').write_text('{}')
        (self.root / 'real').symlink_to(other, target_is_directory=True)
        (group / 'linked').symlink_to(other, target_is_directory=True)
        self.assertEqual(probe.inspect(self.root)['artifacts'], [])
        for path in ('real/private.json', 'synthetic/linked/private.json',
                     'synthetic/work/private.json', 'unlisted/private.json'):
            with self.assertRaises(ValueError):
                self.read(path)

    def test_preview_limits_and_empty_logs(self):
        (self.root / 'empty.log').write_text('')
        self.assertEqual(self.read('empty.log')['content'], '')
        (self.root / 'report.html').write_text('<h1>Report</h1><script>bad()</script>')
        self.assertEqual(self.read('report.html', preview=True)['content'], '<h1>Report</h1>')
        (self.root / 'report.html').write_bytes(b'x' * (probe.PREVIEW_LIMIT + 1))
        with self.assertRaises(ValueError):
            self.read('report.html', preview=True)

    def test_png_jpeg_and_pdf_use_bounded_binary_previews(self):
        fixtures = {'plot.png': (b'\x89PNG\r\n\x1a\nsynthetic', 'image/png', 'png'),
                    'plot.jpg': (b'\xff\xd8\xffsynthetic\xff\xd9', 'image/jpeg', 'jpg'),
                    'report.pdf': (b'%PDF-1.4\n% synthetic\n%%EOF', 'application/pdf', 'pdf')}
        for path, (content, mime, kind) in fixtures.items():
            (self.root / path).write_bytes(content)
            result = self.read(path, preview=True)
            self.assertEqual(result['mime'], mime)
            self.assertEqual(result['kind'], kind)
            self.assertEqual(base64.b64decode(result['content']), content)
            with self.assertRaises(ValueError):
                self.read(path)
        details = {item['path']: item for item in probe.inspect(self.root)['artifact_details']}
        self.assertTrue(all(details[path]['group'] == 'figures' for path in fixtures))
        (self.root / 'fake.png').write_text('<script>alert(1)</script>')
        with self.assertRaises(ValueError):
            self.read('fake.png', preview=True)

    def test_component_health_keeps_failure_signals_separate(self):
        (self.root / 'trace.tsv').write_text('name\tstatus\tnative_id\nstep\tFAILED\t1\n')
        (self.root / 'coordinator.exit').write_text('1\n')
        (self.root / 'run_manifest.json').write_text('{"status":"complete"}')
        data = probe.inspect(self.root)
        self.assertEqual(data['health']['trace']['state'], 'failed')
        self.assertEqual(data['health']['exit_logs']['state'], 'failed')
        self.assertEqual(data['health']['manifests']['state'], 'available')
        self.assertEqual(data['health']['files']['state'], 'available')
        self.assertEqual(data['overall_state'], 'failed')

    def test_artifact_disappearing_during_inspection_marks_files_partial(self):
        (self.root / 'report.html').write_text('<h1>Report</h1>')
        with patch.object(probe, 'artifact_details', return_value=[]):
            data = probe.inspect(self.root)
        self.assertEqual(data['health']['files']['state'], 'partial')
        self.assertEqual(data['health']['files']['unavailable'], 1)
        self.assertEqual(data['overall_state'], 'partial')

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
