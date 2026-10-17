"""Small SE/PE functional fixture; not a benchmark or biological study."""
import argparse
import csv
import gzip
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
ADAPTER = 'AGATCGGAAGAGC'


def unpack(path):
    with gzip.open(path, 'rt') as handle:
        return handle.read()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--stub', action='store_true')
    args = parser.parse_args()
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    inputs = root / 'input'
    inputs.mkdir()
    rng = random.Random(102)
    genome = ''.join(rng.choice('ACGT') for _ in range(4000))
    reference = inputs / 'reference.fa'
    reference.write_text('>fixture\n' + genome + '\n')
    rows = []
    for layout in ('se', 'pe'):
        for role in ('input', 'ip'):
            identifier = f'{layout}.{role}'
            meta = dict(id=identifier, sample_id=identifier, dataset='trim_fixture', genome_id='fixture_v1',
                        single_end=layout == 'se', is_control=role == 'input',
                        control_id='' if role == 'input' else f'{layout}.input', target='input' if role == 'input' else 'H3K4me3',
                        biological_replicate='1', technical_replicate='1', condition='fixture')
            paths = []
            for mate in range(1, 2 if layout == 'se' else 3):
                lines = []
                for number, start in enumerate((100, 300, 500)):
                    sequence = genome[start:start+60]
                    if mate == 2:
                        sequence = sequence.translate(str.maketrans('ACGT', 'TGCA'))[::-1]
                    sequence += ADAPTER
                    lines += [f'@{identifier}.{number}/{mate}', sequence, '+', 'I' * len(sequence)]
                path = inputs / f'{identifier}_R{mate}.fastq.gz'
                with gzip.GzipFile(filename=str(path), mode='wb', mtime=0) as handle:
                    handle.write(('\n'.join(lines) + '\n').encode())
                paths.append(str(path))
            rows.append({'meta': meta, 'reads': paths})
    samples = inputs / 'samples.json'
    samples.write_text(json.dumps(rows))
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs.iterdir()}
    nextflow = os.environ.get('NEXTFLOW_BIN') or shutil.which('nextflow')
    if not nextflow:
        raise RuntimeError('official Nextflow launcher is required')
    results = []

    def run(name, enabled, quality=20, resume=False):
        case = root / name
        case.mkdir(exist_ok=True)
        attempt = len(list(case.glob('console.*.log')))
        trace = case / f'trace.{attempt}.tsv'
        command = [nextflow, '-log', str(case / f'nextflow.{attempt}.log'), 'run',
                   str(ROOT / 'tests/native_chipseq_trimming/main.nf'), '-ansi-log', 'false',
                   '-work-dir', str(case / 'work'), '--samples', str(samples), '--reference', str(reference),
                   '--trim_enabled', str(enabled).lower(), '--trim_quality', str(quality),
                   '--outdir', str(case / 'results'), '-with-trace', str(trace)]
        if args.stub:
            command.append('-stub-run')
        if resume:
            command.append('-resume')
        completed = subprocess.run(command, cwd=case, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (case / f'console.{attempt}.log').write_text(completed.stdout)
        if completed.returncode:
            raise AssertionError(f'{name} failed; see {case}/console.{attempt}.log')
        with trace.open() as handle:
            tasks = list(csv.DictReader(handle, delimiter='\t'))
        if not tasks:
            raise AssertionError('empty trace')
        results.append({'case': name, 'quality': quality, 'resume': resume, 'status': 'PASS',
                        'tasks': [{'name': row['name'], 'status': row['status']} for row in tasks]})
        return tasks

    raw = run('raw', False)
    if any('TRIMMING' in row['name'] or 'TRIM_GALORE' in row['name'] or 'FASTQC_POST' in row['name'] for row in raw):
        raise AssertionError('disabled trimming scheduled a trimming task')
    trimmed = run('trimmed', True)
    if not any('TRIM_GALORE_SINGLE' in row['name'] for row in trimmed) or not any('TRIM_GALORE (' in row['name'] for row in trimmed):
        raise AssertionError('SE or PE trimmer not executed')
    if not args.stub:
        manifests = list((root / 'trimmed/results/pipeline_info/native_qc/read_trimming').glob('*.trimming.manifest.json'))
        if len(manifests) != 4:
            raise AssertionError('missing per-record trimming manifests')
        by_id = {row['meta']['id']: row for row in rows}
        for path in manifests:
            document = json.loads(path.read_text())
            expected = by_id[document['record_id']]['meta']
            for key in expected:
                if key != 'id' and document.get(key) != expected[key]:
                    raise AssertionError(f'metadata changed: {key}')
            if document['reads'][0]['records'] != 3 or document['reads'][0]['bases'] != 180:
                raise AssertionError('fixture trimming did not remove the known adapter')
            for read in document['reads']:
                output = root / 'trimmed/results/trimmed_reads' / document['record_id'] / read['name']
                if hashlib.sha256(output.read_bytes()).hexdigest() != read['sha256']:
                    raise AssertionError('published trimmed FASTQ checksum mismatch')
        # Equivalent direct Trim Galore calls check shared module orchestration,
        # not an alternative algorithm or a performance/biological benchmark.
        direct = root / 'direct'
        direct.mkdir()
        for row in rows:
            command = ['trim_galore', '--gzip', '--quality', '20', '--length', '20', '--adapter', ADAPTER,
                       '--cores', '1', '--output_dir', str(direct)]
            if not row['meta']['single_end']:
                command.append('--paired')
            with (direct / f"{row['meta']['id']}.log").open('w') as log:
                subprocess.run(command + row['reads'], stdout=log, stderr=subprocess.STDOUT, check=True)
            for mate, raw_path in enumerate(row['reads'], 1):
                stem = Path(raw_path).name.removesuffix('.fastq.gz')
                suffix = '_trimmed.fq.gz' if row['meta']['single_end'] else f'_val_{mate}.fq.gz'
                native = root / 'trimmed/results/trimmed_reads' / row['meta']['id'] / f"{row['meta']['id']}.trimmed_R{mate}.fq.gz"
                if unpack(direct / (stem + suffix)) != unpack(native):
                    raise AssertionError('native/direct trimmed FASTQ records differ')
        multiqc = root / 'trimmed/results/pipeline_info/native_qc/multiqc/results/fixture_multiqc.html'
        if not multiqc.is_file() or multiqc.stat().st_size == 0:
            raise AssertionError('MultiQC report missing')
        for case in ('raw', 'trimmed'):
            bams = list((root / case / 'results/alignment').glob('*/*.sorted.bam'))
            if len(bams) != len(rows):
                raise AssertionError(f'{case}: missing aligned BAMs')
            for bam in bams:
                subprocess.run(['samtools', 'quickcheck', str(bam)], check=True)
                if case == 'trimmed':
                    identifier = bam.name.removesuffix('.sorted.bam')
                    expected_count = 3 if by_id[identifier]['meta']['single_end'] else 6
                    count = int(subprocess.check_output(['samtools', 'view', '-c', '-F', '4', str(bam)], text=True))
                    if count != expected_count:
                        raise AssertionError('known trimmed fixture reads did not align')
        cached = run('trimmed', True, resume=True)
        if any(row['status'] != 'CACHED' for row in cached):
            raise AssertionError('identical fixture resume reran eligible tasks')
        changed = run('trimmed', True, quality=25, resume=True)
        if not any('TRIM_GALORE' in row['name'] and row['status'] == 'COMPLETED' for row in changed):
            raise AssertionError('quality change did not rerun trimming')
        if any(row['status'] != 'CACHED' for row in changed if 'FASTQC_RAW' in row['name'] or 'BOWTIE2_INDEX (' in row['name']):
            raise AssertionError('quality change reran raw QC or reference indexing')
    if before != {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs.iterdir()}:
        raise AssertionError('raw inputs changed')
    (root / 'validation.json').write_text(json.dumps({'status': 'PASS', 'stub': args.stub, 'benchmark': False,
        'cases': results, 'raw_inputs_unchanged': True}, indent=2) + '\n')
    print(json.dumps({'status': 'PASS', 'stub': args.stub, 'benchmark': False}))


if __name__ == '__main__':
    main()
