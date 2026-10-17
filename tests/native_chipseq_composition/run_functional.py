"""Reduced stage-composition checks; never a biological/performance benchmark."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from generate_fixture import generate

ROOT = Path(__file__).resolve().parents[2]
UPSTREAM = ('FASTQC', 'MULTIQC', 'BOWTIE2', 'BAM_SELECT', 'BAM_DUPLICATES', 'BAM_BLACKLIST', 'BAM_INDEX_QC', 'MACS3', 'PEAK_CALLING', 'CONSENSUS_CONTEXT', 'CONSENSUS_UNION', 'IDR_PROVIDER')
DB = ('DB_PREFLIGHT', 'PEAK_COUNTING', 'DESEQ2_DB_', 'DB_AGGREGATE')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--stub', action='store_true')
    parser.add_argument('--only-full', action='store_true', help='Run only the full off/on composition checks')
    args = parser.parse_args()
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    nextflow = os.environ.get('NEXTFLOW_BIN') or shutil.which('nextflow')
    if not nextflow:
        raise RuntimeError('official Nextflow launcher is required')
    records = []

    def run(name, options, resume=False, expected_failure=None):
        case = root / name
        case.mkdir(exist_ok=True)
        attempt = len(list(case.glob('console.*.log')))
        trace = case / f'trace.{attempt}.tsv'
        command = [nextflow, '-log', str(case / f'nextflow.{attempt}.log'), 'run', str(ROOT / 'main.nf'),
                   '-profile', 'test', '-c', str(ROOT / 'tests/native_chipseq_composition/fixture.config'),
                   '-ansi-log', 'false', '-work-dir', str(case / 'work'), '-with-trace', str(trace),
                   '--workflow', 'chipseq', '--outdir', str(case / 'results')] + options
        if args.stub:
            command.append('-stub-run')
        if resume:
            command.append('-resume')
        result = subprocess.run(command, cwd=case, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (case / f'console.{attempt}.log').write_text(result.stdout)
        with trace.open() as handle:
            tasks = list(csv.DictReader(handle, delimiter='\t'))
        if not tasks:
            raise AssertionError('empty execution trace')
        if expected_failure:
            if result.returncode == 0 or expected_failure not in result.stdout:
                raise AssertionError(f'{name}: expected input rejection; inspect console.{attempt}.log')
        elif result.returncode:
            raise AssertionError(f'{name}: workflow failed; inspect console.{attempt}.log')
        records.append(dict(case=name, attempt=attempt, expected_rejection=bool(expected_failure),
                            tasks=[dict(name=row['name'], status=row['status']) for row in tasks]))
        return tasks

    def assert_no(tasks, names):
        if any(token in row['name'] for row in tasks for token in names):
            raise AssertionError(f'unexpected producer in trace: {names}')

    if not args.only_full:
        fixture = generate(root / 'accepted', real=not args.stub, status='stub' if args.stub else 'complete')
        before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in fixture.iterdir() if p.is_file()}
        for kind in ('consensus', 'idr'):
            tasks = run(kind, ['--chipseq_run_mode', 'post_consensus', '--chipseq_continuation_manifest', str(fixture / f'{kind}_input.json')])
            assert_no(tasks, UPSTREAM + DB)
            terminal = json.loads((root / kind / 'results/chipseq/chipseq_run_manifest.json').read_text())
            if terminal['contrasts'] or any(a['artifact_type'] == 'differential_binding' for a in terminal['artifacts']):
                raise AssertionError('continuation fabricated differential binding')
            if terminal['provenance']['parameters']['differential_binding'] != 'not_requested':
                raise AssertionError('terminal omission status missing')
            kinds = {a['artifact_type'] for a in terminal['artifacts']}
            if not {'peak_gene_annotation', 'signal_track', 'chipseq_report', 'aligned_bam', 'idr_peaks' if kind == 'idr' else 'consensus_peaks'} <= kinds:
                raise AssertionError('incomplete continuation terminal inventory')
            if f'fixture.{kind}' not in terminal['provenance']['source_manifest_ids']:
                raise AssertionError('original producer identity lost')
            report_inventory = root / kind / 'results/pipeline_info/native_chipseq/full/chipseq_full_report_input.json'
            if not args.stub:
                report = json.loads((root / kind / 'results/chipseq/report/report_result/report.json').read_text())
                if report['sections']['differential_binding']['status'] != 'not_requested':
                    raise AssertionError('report incorrectly claims DB results')
            report_tasks = run(f'{kind}-report', ['--chipseq_run_mode', 'report', '--chipseq_report_input_manifest', str(report_inventory)])
            if len(report_tasks) != 3 or any(':CHIPSEQ_REPORT:' not in row['name'] for row in report_tasks):
                raise AssertionError('report-only re-entry started a scientific producer')
    
        bad_inventory = json.loads((fixture / 'consensus_input.json').read_text())
        bad_reference = json.loads((fixture / 'reference.json').read_text())
        bad_reference['genome_id'] = 'incompatible'
        (fixture / 'bad_reference.json').write_text(json.dumps(bad_reference))
        bad_inventory['reference']['manifest'] = 'bad_reference.json'
        (fixture / 'bad_input.json').write_text(json.dumps(bad_inventory))
        rejected = run('rejected', ['--chipseq_run_mode', 'post_consensus', '--chipseq_continuation_manifest', str(fixture / 'bad_input.json')],
                       expected_failure='reference identity mismatch')
        if len(rejected) != 1 or 'CHIPSEQ_CONTINUATION_CONTEXT' not in rejected[0]['name']:
            raise AssertionError('incompatible inputs reached a downstream producer')
        after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in fixture.iterdir() if p.name in before}
        if before != after:
            raise AssertionError('accepted input artifacts changed')

    full_root = root / 'full-fixture'
    subprocess.run([sys.executable, str(ROOT / 'tests/slurm/generate_chipseq_production_fixture.py'), '--case-root', str(full_root)], check=True)
    full_options = ['--chipseq_run_mode', 'full', '--chipseq_config', str(full_root / 'pipeline_config.sh'),
                    '--chipseq_db_spec', str(full_root / 'db_spec.json')]
    disabled = run('full', full_options + ['--chipseq_db_enabled', 'false'])
    assert_no(disabled, DB)
    doc = json.loads((root / 'full/results/chipseq/chipseq_run_manifest.json').read_text())
    if doc['contrasts'] or doc['provenance']['parameters']['differential_binding'] != 'not_requested':
        raise AssertionError('full without DB invented inference')
    expected_types = {'aligned_bam', 'peak_set', 'peak_qc', 'consensus_peaks', 'peak_gene_annotation', 'signal_track', 'chipseq_report'}
    if not expected_types <= {a['artifact_type'] for a in doc['artifacts']}:
        raise AssertionError('full without DB did not deliver all requested components')
    enabled = run('full', full_options + ['--chipseq_db_enabled', 'true'], resume=True)
    if not any('DB_PREFLIGHT' in task['name'] for task in enabled):
        raise AssertionError('explicit DB request was not executed')
    producer_tokens = ('FASTQC', 'BOWTIE2', 'MACS3')
    initial = {task['name'] for task in disabled if any(token in task['name'] for token in producer_tokens)}
    reused = [task for task in enabled if any(token in task['name'] for token in producer_tokens)]
    if not initial or initial != {task['name'] for task in reused} or any(task['status'] != 'CACHED' for task in reused):
        raise AssertionError('compatible scientific producers were restarted when enabling DB')
    doc = json.loads((root / 'full/results/chipseq/chipseq_run_manifest.json').read_text())
    if not args.stub and (not doc['contrasts'] or not any(a['artifact_type'] == 'differential_binding' for a in doc['artifacts'])):
        raise AssertionError('DB-enabled terminal results missing')
    (root / 'validation.json').write_text(json.dumps(dict(status='PASS', benchmark=False, stub=args.stub,
        accepted_inputs_unchanged=None if args.only_full else True, scope='full' if args.only_full else 'all', cases=records), indent=2) + '\n')
    print(json.dumps(dict(status='PASS', benchmark=False, stub=args.stub)))


if __name__ == '__main__':
    main()
