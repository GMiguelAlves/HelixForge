"""Portable Bowtie2 index provenance and strict prebuilt-bundle validation."""
import argparse
import base64
import hashlib
import json
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

SUFFIXES = ('1', '2', '3', '4', 'rev.1', 'rev.2')


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def shards(directory, basename):
    if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]*', basename):
        raise ValueError('unsafe index basename')
    directory = Path(directory)
    candidates = []
    for extension in ('bt2', 'bt2l'):
        names = {f'{basename}.{suffix}.{extension}' for suffix in SUFFIXES}
        if all((directory / name).is_file() and (directory / name).stat().st_size for name in names):
            candidates.append(names)
    found = {p.name for p in directory.iterdir() if p.name.endswith(('.bt2', '.bt2l'))}
    if len(candidates) != 1 or found != candidates[0]:
        raise ValueError('index requires exactly six nonempty, unmixed .bt2 or .bt2l shards for its basename')
    return {name: sha256(directory / name) for name in sorted(candidates[0])}


def tool_version(executable='bowtie2'):
    result = subprocess.run([executable, '--version'], capture_output=True, text=True, check=True)
    match = re.search(r'version\s+(\d+\.\d+\.\d+(?:[.-][A-Za-z0-9]+)?)', result.stdout)
    if not match:
        raise ValueError('could not determine Bowtie2 version')
    return match.group(1)


def bundle_document(directory, reference, meta, parameters, version):
    files = shards(directory, parameters.get('basename', 'genome'))
    return {
        'schema_version': '1.2', 'type': 'alignment_index', 'status': 'complete',
        'id': meta['id'], 'aligner': 'bowtie2', 'artifact': 'bowtie2_index',
        'genome_id': meta.get('genome_id'), 'basename': parameters.get('basename', 'genome'),
        'reference_sha256': sha256(reference), 'bowtie2_version': version,
        'index_parameters': {'extra_args': shlex.split(parameters.get('extra_args') or '')},
        'files': files,
        'bundle_sha256': hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest(),
        'index_source': 'built',
    }


def validate_bundle(directory, reference, source, meta, parameters, runtime_version):
    if not isinstance(source, dict) or source.get('schema_version') != '1.2' or source.get('type') != 'alignment_index':
        raise ValueError('prebuilt index needs an alignment_index schema 1.2 provenance manifest')
    if source.get('aligner') != 'bowtie2' or source.get('status') != 'complete':
        raise ValueError('prebuilt index must be complete and produced by Bowtie2')
    if source.get('basename') != parameters.get('basename', 'genome'):
        raise ValueError('index basename differs from the configured basename')
    if source.get('reference_sha256') != sha256(reference):
        raise ValueError('reference checksum differs from the index manifest')
    if meta.get('genome_id') and source.get('genome_id') != meta['genome_id']:
        raise ValueError('genome identity differs from the index manifest')
    if source.get('bowtie2_version') != runtime_version:
        raise ValueError('Bowtie2 version mismatch: exact build/runtime version match required')
    if source.get('index_parameters') != {'extra_args': shlex.split(parameters.get('extra_args') or '')}:
        raise ValueError('index build parameters differ from the manifest')
    actual = shards(directory, source['basename'])
    if source.get('files') != actual:
        raise ValueError('index shard names or checksums differ from the manifest')
    checksum = hashlib.sha256(json.dumps(actual, sort_keys=True).encode()).hexdigest()
    if source.get('bundle_sha256') != checksum:
        raise ValueError('portable index bundle checksum differs from the manifest')
    result = dict(source)
    result.update(id=meta['id'], index_source='prebuilt', source_id=source.get('id'),
                  compatibility_policy='exact_bowtie2_version_reference_and_build_arguments')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['build-manifest', 'validate'])
    parser.add_argument('--index', required=True)
    parser.add_argument('--reference', required=True)
    parser.add_argument('--request-base64', required=True)
    parser.add_argument('--source-manifest')
    parser.add_argument('--output', required=True)
    parser.add_argument('--legacy-sha256')
    parser.add_argument('--execution-output')
    args = parser.parse_args()
    request = json.loads(base64.b64decode(args.request_base64))
    started = time.time()
    version = tool_version()
    if args.mode == 'build-manifest':
        document = bundle_document(args.index, args.reference, request['meta'], request['parameters'], version)
        if args.legacy_sha256:
            document['sha256'] = args.legacy_sha256
    else:
        if not args.source_manifest:
            parser.error('--source-manifest is required for validation')
        source = json.loads(Path(args.source_manifest).read_text(encoding='utf-8'))
        document = validate_bundle(args.index, args.reference, source, request['meta'], request['parameters'], version)
        document['source_manifest_sha256'] = sha256(args.source_manifest)
        document['validation_elapsed_seconds'] = time.time() - started
    Path(args.output).write_text(json.dumps(document, indent=2) + '\n', encoding='utf-8')
    print(f"PASS: Bowtie2 index {document['index_source']}; bundle_sha256={document['bundle_sha256']}")
    if args.execution_output:
        execution = {
            'process': 'BOWTIE2_INDEX_VALIDATE', 'status': 'complete', 'index_source': 'prebuilt',
            'id': request['meta']['id'], 'reference_sha256': document['reference_sha256'],
            'bundle_sha256': document['bundle_sha256'], 'bowtie2_version': version,
            'source_manifest_sha256': document['source_manifest_sha256'],
            'started_epoch': started, 'ended_epoch': time.time(),
            'elapsed_seconds': time.time() - started,
            'resources': request.get('resources', {}),
            'command': sys.argv,
        }
        Path(args.execution_output).write_text(json.dumps(execution, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        sys.exit(2)
