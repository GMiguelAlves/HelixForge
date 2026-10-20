"""Reduced real/stub/cache integration checks; no biological benchmark."""
import argparse
import csv
import json
import os
from pathlib import Path
import shutil
import subprocess
from generate_fixture import generate
from validate_real import validate

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--stub', action='store_true')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    generate(output/'fixture')
    launcher = os.environ.get('NEXTFLOW_BIN') or shutil.which('nextflow')
    if not launcher:
        raise RuntimeError('official Nextflow launcher is required')
    runs = []
    for attempt in range(2):
        trace = output/f'trace.{attempt}.tsv'
        command = [launcher,'-log',str(output/f'nextflow.{attempt}.log'),'run',str(ROOT/'tests/native_chipseq_nfcore/main.nf'),
                   '-c',str(ROOT/'tests/native_chipseq_nfcore/nextflow.config'),'-ansi-log','false',
                   '--fixture_dir',str(output/'fixture'),'--outdir',str(output/'results'),
                   '-work-dir',str(output/'work'),'-with-trace',str(trace)]
        if args.stub:
            command.append('-stub-run')
        if attempt:
            command.append('-resume')
        result = subprocess.run(command, cwd=output, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        (output/f'console.{attempt}.log').write_text(result.stdout)
        if result.returncode:
            raise AssertionError(f'workflow failed: console.{attempt}.log')
        with trace.open() as handle:
            tasks = list(csv.DictReader(handle, delimiter='\t'))
        if len(tasks) != 8:
            raise AssertionError(f'expected eight processes, found {len(tasks)}')
        if attempt and any(task['status'] != 'CACHED' for task in tasks):
            raise AssertionError('identical execution did not reuse every task')
        if not attempt and any(task['status'] != 'COMPLETED' for task in tasks):
            raise AssertionError('first execution did not complete every task')
        runs.append(dict(attempt=attempt, tasks=len(tasks), cached=sum(t['status']=='CACHED' for t in tasks)))
    if not args.stub:
        validate(output/'fixture', output/'results', output/'direct')
    (output/'validation.json').write_text(json.dumps(dict(status='PASS', benchmark=False, stub=args.stub, runs=runs), indent=2)+'\n')
    print(json.dumps(dict(status='PASS', stub=args.stub, runs=runs)))


if __name__ == '__main__':
    main()
