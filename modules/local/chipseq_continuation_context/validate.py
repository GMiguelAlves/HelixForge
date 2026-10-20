"""Validate declared post-consensus inputs; never discover result directories."""
import argparse
import base64
import csv
import hashlib
import json
from pathlib import Path
import re


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def validate(request, paths, stub=False):
    checksums = {}
    def path(index):
        if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(paths):
            raise ValueError('invalid declared artifact index')
        value = Path(paths[index])
        if not value.is_file():
            raise ValueError(f'declared input is missing: {value.name}')
        return value

    def document(index):
        result = json.loads(path(index).read_text())
        if not isinstance(result, dict) or not result.get('id') or result.get('status') not in ({'complete', 'complete_empty', 'stub'} if stub else {'complete', 'complete_empty'}):
            raise ValueError('source manifest must identify a completed producer')
        return result

    def checked(index, expected, label):
        value = path(index)
        if not stub:
            if index not in checksums:
                checksums[index] = sha256(value)
            if not isinstance(expected, str) or not re.fullmatch(r'[a-fA-F0-9]{64}', expected) or checksums[index] != expected.lower():
                raise ValueError(f'{label} checksum missing or different')

    project = request['project']
    if any(not isinstance(project.get(key), str) or not project[key].strip() for key in ('project_id', 'dataset', 'genome_id', 'build')):
        raise ValueError('continuation requires explicit project/dataset/genome/build')
    ref = request['reference']
    ref_doc = document(ref['manifest'])
    if ref_doc.get('type') not in {'reference_bundle', 'reference'} or ref_doc.get('genome_id') != project['genome_id'] or ref_doc.get('build') != project['build'] or not ref_doc.get('organism'):
        raise ValueError('reference identity mismatch')
    for role, aliases in [('fasta', ('reference', 'fasta', 'genome')), ('annotation', ('annotation',))]:
        artifact = next((ref_doc.get('artifacts', {}).get(key) for key in aliases if key in ref_doc.get('artifacts', {})), {})
        checked(ref[role], artifact.get('sha256'), role)
    metadata = request['metadata']
    metadata_doc = document(metadata['manifest'])
    if metadata_doc.get('type') != 'chipseq_metadata':
        raise ValueError('a normalized ChIP metadata manifest is required')
    checked(metadata['table'], metadata_doc.get('artifacts', {}).get('metadata', {}).get('sha256'), 'metadata')
    with path(metadata['table']).open(newline='') as handle:
        rows = list(csv.DictReader(handle, delimiter='\t'))
    by_id = {}
    for row in rows:
        identifier = row.get('record_id', '')
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', identifier) or identifier in by_id:
            raise ValueError('invalid or duplicate metadata record ID')
        if row.get('dataset') != project['dataset'] or row.get('genome_id') != project['genome_id']:
            raise ValueError('metadata dataset/reference mismatch')
        if not all(row.get(key) for key in ('sample_id', 'condition', 'target', 'biological_replicate', 'technical_replicate')):
            raise ValueError('metadata lacks biological/technical identity')
        by_id[identifier] = row
    if not by_id:
        raise ValueError('empty continuation metadata')
    records = request['records']
    if not records or {r['record_id'] for r in records} != set(by_id) or len(records) != len(by_id):
        raise ValueError('declared BAM records must match metadata exactly')
    source_ids = {ref_doc['id'], metadata_doc['id']}
    for record in records:
        row = by_id[record['record_id']]
        doc = document(record['manifest'])
        if doc.get('type') != 'bam_final' or doc.get('record_id') != row['record_id']:
            raise ValueError('final BAM manifest record mismatch')
        for key in ('sample_id', 'dataset', 'condition', 'target', 'genome_id'):
            if doc.get(key) != row[key]:
                raise ValueError(f'final BAM metadata conflict: {key}')
        checked(record['bam'], doc.get('sha256'), 'BAM')
        checked(record['bai'], doc.get('index_sha256'), 'BAI')
        if not stub and doc.get('reference_sha256') != checksums[ref['fasta']]:
            raise ValueError('BAM reference checksum mismatch')
        record['meta'] = {key: row[key] for key in ('record_id', 'sample_id', 'dataset', 'condition', 'target', 'genome_id', 'biological_replicate', 'technical_replicate')}
        record['meta'].update(id=row['record_id'], source_manifest_id=doc['id'], is_control=row.get('is_control', '').lower() in {'true', '1', 'yes', 'y'})
        if not record['meta']['is_control']:
            control = row.get('control_id') or row.get('control_record_id')
            if control and (control not in by_id or by_id[control].get('is_control', '').lower() not in {'true', '1', 'yes', 'y'}):
                raise ValueError('invalid declared IP/control relationship')
        source_ids.add(doc['id'])
    peaks = request['peaks']
    if not peaks:
        raise ValueError('at least one accepted consensus/IDR peak set is required')
    peak_ids = set()
    for entry in peaks:
        doc = document(entry['manifest'])
        if doc.get('type') not in {'consensus', 'idr'} or doc['id'] in peak_ids:
            raise ValueError('unique consensus/IDR provider manifests are required')
        peak_ids.add(doc['id'])
        allowed = {'idr'} if doc['type'] == 'idr' else {'union', 'intersection', 'replicate_support', 'nfcore_2_1'}
        if doc.get('strategy') not in allowed or doc.get('replicate_mode') not in {'biological', 'technical'}:
            raise ValueError('peak strategy/replicate mode is not declared consistently')
        if doc.get('build') not in (None, project['build']) or doc.get('organism') not in (None, ref_doc['organism']):
            raise ValueError('peak reference identity mismatch')
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', doc['id']):
            raise ValueError('unsafe peak-set identifier')
        for key in ('dataset', 'genome_id'):
            if doc.get(key) != project[key]:
                raise ValueError('peak set project/reference mismatch')
        artifact = doc.get('artifacts', {}).get('consolidated_bed') or doc.get('artifacts', {}).get('consolidated_peaks') or {}
        checked(entry['peaks'], artifact.get('sha256'), 'consolidated peaks')
        if doc.get('strategy') == 'nfcore_2_1':
            index = entry.get('evidence_bundle')
            if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(paths):
                raise ValueError('nfcore_2_1 continuation requires an explicit evidence_bundle')
            bundle = Path(paths[index])
            if not bundle.is_dir() or not (bundle / 'manifest.json').is_file():
                raise ValueError('consensus evidence_bundle must contain its manifest')
            if not stub and sha256(bundle / 'manifest.json') != sha256(path(entry['manifest'])):
                raise ValueError('consensus evidence bundle identity mismatch')
        replicates = doc.get('replicates', [])
        if not replicates or len({r.get('record_id') for r in replicates}) != len(replicates):
            raise ValueError('peak set lacks unique biological/technical identities')
        for replicate in replicates:
            row = by_id.get(replicate.get('record_id'))
            if row is None:
                raise ValueError('peak replicate has no declared final BAM')
            for key in ('sample_id', 'condition', 'biological_replicate', 'technical_replicate'):
                if str(replicate.get(key) or '') != row[key]:
                    raise ValueError(f'peak replicate metadata conflict: {key}')
            if row['target'] != doc.get('target') or row['condition'] != doc.get('condition') or row.get('is_control', '').lower() in {'true', '1', 'yes', 'y'}:
                raise ValueError('peak set mark/condition/IP mismatch')
        entry['meta'] = {key: doc.get(key) for key in ('id', 'dataset', 'condition', 'target', 'genome_id', 'peak_type', 'organism')}
        entry['meta'].update(artifact_type='idr_peaks' if doc['type'] == 'idr' else 'consensus_peaks', sample_ids=[r['sample_id'] for r in replicates])
        source_ids.add(doc['id'])
    # Additional explicitly supplied QC/alignment manifests must be compatible.
    for index in request.get('source_manifests', []):
        doc = document(index)
        for key in ('dataset', 'genome_id', 'build'):
            if doc.get(key) not in (None, project[key]):
                raise ValueError(f'source manifest {key} mismatch')
        if doc.get('type') in {'differential_binding', 'differential_binding_contrast'}:
            raise ValueError('post-consensus continuation does not request Differential Binding')
        source_ids.add(doc['id'])
    request.update(schema_version='1.0', type='chipseq_continuation_plan',
                   status='stub' if stub else 'complete', differential_binding='not_requested',
                   source_manifest_ids=sorted(source_ids))
    return request


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--request', required=True)
    parser.add_argument('--paths', required=True)
    parser.add_argument('--stub', action='store_true')
    args = parser.parse_args()
    result = validate(json.loads(base64.b64decode(args.request)), json.loads(base64.b64decode(args.paths)), args.stub)
    Path('continuation.plan.json').write_text(json.dumps(result, indent=2) + '\n')
    print('Continuation inputs validated' if not args.stub else 'STUB: artifact integrity not certified')


if __name__ == '__main__':
    main()
