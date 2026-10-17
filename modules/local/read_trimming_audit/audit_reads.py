"""Validate FASTQ integrity/pairing and record optional read-trimming provenance."""
import argparse
import base64
import gzip
import hashlib
import itertools
import json
from pathlib import Path
import platform
import re
import sys
import time


def policy(quality, length, adapter=None, adapter2=None):
    if isinstance(quality, bool) or not re.fullmatch(r'\d+', str(quality)) or not 0 <= int(quality) <= 40:
        raise ValueError('trimming quality must be an explicit integer in 0..40')
    if isinstance(length, bool) or not re.fullmatch(r'\d+', str(length)) or int(length) < 1:
        raise ValueError('trimming minimum length must be an explicit positive integer')
    for sequence in (adapter, adapter2):
        if sequence is not None and not re.fullmatch(r'[ACGTRYSWKMBDHVNacgtryswkmbdhvn]+', str(sequence)):
            raise ValueError('adapter must contain only DNA IUPAC bases')
    if adapter2 and not adapter:
        raise ValueError('adapter2 requires an explicit adapter for read1')
    return {'quality': int(quality), 'minimum_length': int(length), 'adapter': adapter,
            'adapter2': adapter2, 'adapter_mode': 'explicit' if adapter else 'trim_galore_auto_detection'}


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def fastq_records(path):
    path = Path(path)
    with path.open('rb') as handle:
        compressed = handle.read(2) == b'\x1f\x8b'
    opener = gzip.open if compressed else open
    with opener(path, 'rt', encoding='ascii', newline='') as handle:
        while True:
            header = handle.readline()
            if not header:
                return
            sequence, separator, qualities = (handle.readline().rstrip('\r\n') for _ in range(3))
            if not header.startswith('@') or not separator.startswith('+') or not sequence or len(sequence) != len(qualities):
                raise ValueError('malformed FASTQ record: header, sequence, separator or quality length')
            if not re.fullmatch(r'[ACGTRYSWKMBDHVNacgtryswkmbdhvn.]+', sequence) or any(not 33 <= ord(c) <= 126 for c in qualities):
                raise ValueError('invalid FASTQ sequence or quality characters')
            tokens = header[1:].split()
            if not tokens:
                raise ValueError('FASTQ read identifier is empty')
            identifier = re.sub(r'/[12]$', '', tokens[0])
            if not identifier:
                raise ValueError('FASTQ read identifier is empty')
            mate = tokens[0][-1] if re.search(r'/[12]$', tokens[0]) else None
            if len(tokens) > 1 and re.match(r'^[12]:', tokens[1]):
                illumina_mate = tokens[1][0]
                if mate and mate != illumina_mate:
                    raise ValueError('conflicting FASTQ mate labels')
                mate = illumina_mate
            yield identifier, len(sequence), mate


def inspect_reads(reads, single_end):
    if len(reads) != (1 if single_end else 2):
        raise ValueError('FASTQ cardinality does not match library layout')
    if len({Path(p).resolve() for p in reads}) != len(reads):
        raise ValueError('paired FASTQs must be distinct files')
    counts = [0] * len(reads)
    bases = [0] * len(reads)
    for records in itertools.zip_longest(*(fastq_records(p) for p in reads)):
        if any(record is None for record in records):
            raise ValueError('paired FASTQs have different record counts')
        if not single_end and records[0][0] != records[1][0]:
            raise ValueError('paired FASTQs have mismatched read identifiers')
        for index, (_identifier, length, mate) in enumerate(records):
            if not single_end and mate and mate != str(index + 1):
                raise ValueError('paired FASTQs have reversed or invalid mate labels')
            counts[index] += 1
            bases[index] += length
    if not counts[0]:
        raise ValueError('FASTQ input contains no reads')
    return [{'mate': index + 1, 'name': Path(path).name, 'records': counts[index],
             'bases': bases[index], 'sha256': sha256(path)} for index, path in enumerate(reads)]


def audit(meta, reads, parameters, prior=None, versions=None):
    selected_policy = policy(parameters.get('quality'), parameters.get('minimum_length'),
                             parameters.get('adapter'), parameters.get('adapter2'))
    if not isinstance(meta.get('single_end'), bool):
        raise ValueError('single_end must be a boolean')
    if meta['single_end'] and selected_policy['adapter2']:
        raise ValueError('single-end libraries cannot specify adapter2')
    observed = inspect_reads(reads, meta['single_end'])
    result = {key: meta[key] for key in ('dataset', 'genome_id', 'organism', 'sample_id', 'condition',
              'target', 'is_control', 'control_id', 'biological_replicate', 'technical_replicate') if key in meta}
    result.update(schema_version='1.0', type='read_trimming' if prior else 'read_validation',
                  id=meta['id'] + ('.trimming' if prior else '.raw_validation'), record_id=meta['id'],
                  status='complete', provider='trim_galore', single_end=meta['single_end'],
                  policy=selected_policy, reads=observed, read_processing='trimmed' if prior else 'raw',
                  versions={'python': platform.python_version(), **(versions or {})})
    if prior:
        if prior.get('record_id') != meta['id'] or prior.get('policy') != selected_policy or prior.get('status') != 'complete':
            raise ValueError('raw preflight identity or policy differs from trimmed input')
        for key in ('dataset', 'genome_id', 'sample_id', 'control_id', 'is_control', 'target',
                    'single_end', 'biological_replicate', 'technical_replicate', 'condition'):
            if prior.get(key) != result.get(key):
                raise ValueError(f'trimming metadata changed: {key}')
        if any(row['records'] > original['records'] for row, original in zip(observed, prior['reads'])):
            raise ValueError('trimmed output contains more records than raw input')
        result['raw_reads'] = prior['reads']
        result['retained_fraction'] = observed[0]['records'] / prior['reads'][0]['records']
        result['input_manifest_id'] = prior['id']
        if not versions or not all(versions.get(tool) for tool in ('trim_galore', 'cutadapt')):
            raise ValueError('trimming tool versions are required')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request-base64', required=True)
    parser.add_argument('--reads', nargs='+', required=True)
    parser.add_argument('--prior')
    parser.add_argument('--versions')
    parser.add_argument('--output', required=True)
    parser.add_argument('--execution', required=True)
    args = parser.parse_args()
    request = json.loads(base64.b64decode(args.request_base64))
    started = time.time()
    versions = {}
    if args.versions:
        for line in Path(args.versions).read_text().splitlines():
            match = re.match(r'\s+(trim_galore|cutadapt):\s*[\"\x27]?([^\s\"\x27]+)', line)
            if match:
                versions[match[1]] = match[2]
    prior = json.loads(Path(args.prior).read_text()) if args.prior else None
    document = audit(request['meta'], args.reads, request['policy'], prior, versions)
    Path(args.output).write_text(json.dumps(document, indent=2) + '\n')
    execution = {'id': document['id'], 'status': 'complete', 'elapsed_seconds': time.time() - started,
                 'resources': request.get('resources'), 'command': sys.argv,
                 'versions': document['versions'], 'read_processing': document['read_processing']}
    Path(args.execution).write_text(json.dumps(execution, indent=2) + '\n')
    print(f"PASS: {document['id']} ({document['reads'][0]['records']} records)")


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, EOFError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        sys.exit(2)
