"""Bounded real-tool validation; run inside a compute allocation on HPC."""
import argparse
import csv
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    fixture = ROOT / 'tests/fixtures/native_alignment'
    nextflow = os.environ.get('NEXTFLOW_BIN') or shutil.which('nextflow')
    if not nextflow:
        raise RuntimeError('official Nextflow launcher not found')
    results = []

    def run(name, extra=(), reuse=False, failure=None):
        case = out / name
        case.mkdir(exist_ok=True)
        command = [nextflow, '-log', str(case / 'nextflow.log'), 'run',
                   str(ROOT / 'tests/native_alignment/main.nf'), '-ansi-log', 'false',
                   '-work-dir', str(case / 'work'), '--aligner', 'bowtie2',
                   '--reference', str(fixture / 'reference.fa'),
                   '--annotation', str(fixture / 'annotation.gtf'),
                   '--read1', str(fixture / 'reads_R1.fastq'),
                   '--read2', str(fixture / 'reads_R2.fastq'),
                   '--target_root', str(case / 'target'), '--outdir', str(case / 'results'),
                   '--trace_file', str(case / 'trace.tsv')]
        if reuse:
            command += ['--prebuilt_index', str(index), '--prebuilt_manifest', str(manifest)]
        command += list(extra)
        completed = subprocess.run(command, cwd=case, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (case / 'console.log').write_text(completed.stdout)
        rows = []
        if (case / 'trace.tsv').exists():
            with (case / 'trace.tsv').open() as handle:
                rows = list(csv.DictReader(handle, delimiter='\t'))
        if failure:
            if completed.returncode == 0 or failure not in completed.stdout:
                raise AssertionError(f'{name}: expected explicit failure {failure!r}; see {case}/console.log')
            if any('BOWTIE2_ALIGN' in r.get('name', '') for r in rows):
                raise AssertionError(f'{name}: alignment ran after invalid index')
        elif completed.returncode:
            raise AssertionError(f'{name}: Nextflow failed; see {case}/console.log')
        results.append({'case': name, 'status': 'PASS', 'expected_failure': failure, 'tasks': len(rows)})
        return rows

    built = run('build')
    if not any('BOWTIE2_INDEX' in r['name'] for r in built):
        raise AssertionError('no index build was observed')
    index = out / 'build/target/bowtie2_index'
    manifest = out / 'build/results/pipeline_info/native_alignment/bowtie2_index/synthetic.bowtie2.index.manifest.json'
    source = json.loads(manifest.read_text())
    baseline_shards = dict(source['files'])
    reused = run('reuse', reuse=True)
    if any('BOWTIE2_INDEX (' in r['name'] for r in reused):
        raise AssertionError('reusing the index unexpectedly built it')
    if not any('BOWTIE2_INDEX_VALIDATE' in r['name'] for r in reused):
        raise AssertionError('index was not validated')
    bam = 'SYNTHETIC.synthetic_sample.bowtie2.alignment.sorted.bam'
    records = []
    for name in ('build', 'reuse'):
        path = out / name / 'target/bowtie2_output' / bam
        records.append(sorted(subprocess.check_output(['samtools', 'view', str(path)], text=True).splitlines()))
    if not records[0] or records[0] != records[1]:
        raise AssertionError('real BAM records are empty or differ')
    resumed = run('reuse', ['-resume'], reuse=True)
    if not resumed or any(r['status'] != 'CACHED' for r in resumed):
        raise AssertionError('identical resume did not cache every eligible task')
    # Independent runs below must fail validation before scheduling alignment.
    run('bad_parameters', ['--index_extra_args', '--offrate 5'], reuse=True, failure='parameters differ')
    altered = out / 'wrong_version.json'
    altered.write_text(json.dumps(dict(source, bowtie2_version='0.0.0')))
    run('bad_version', ['--prebuilt_manifest', str(altered)], reuse=True, failure='version mismatch')
    wrong_reference = out / 'wrong_reference.fa'
    wrong_reference.write_text('>chr1\nACGT\n')
    run('bad_reference', ['--reference', str(wrong_reference)], reuse=True, failure='reference checksum')
    broken = out / 'broken_index'
    shutil.copytree(index, broken)
    (broken / next(iter(baseline_shards))).unlink()
    run('missing_shard', ['--prebuilt_index', str(broken)], reuse=True, failure='exactly six')
    # Original source is still complete and unmodified after all consumers.
    import importlib.util
    spec = importlib.util.spec_from_file_location('bundle', ROOT / 'modules/local/bowtie2_index/index_bundle.py')
    bundle = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bundle)
    if bundle.shards(index, 'genome') != baseline_shards:
        raise AssertionError('original supplied index was modified')
    (out / 'validation.json').write_text(json.dumps({'status': 'PASS', 'bam_records_equal': True,
        'source_unchanged': True, 'cases': results}, indent=2) + '\n')
    print(json.dumps({'status': 'PASS', 'cases': len(results)}))


if __name__ == '__main__':
    main()
