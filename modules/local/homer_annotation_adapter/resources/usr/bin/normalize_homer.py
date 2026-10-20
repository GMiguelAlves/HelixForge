#!/usr/bin/env python3
"""Lossless identity/evidence transport; scientific annotation is HOMER's."""
import argparse
from collections import defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys
import time


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def write_table(path, columns, rows):
    with Path(path).open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter='\t', lineterminator='\n', extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def read_peaks(path):
    result = {}
    for line in Path(path).read_text().splitlines():
        if not line.strip():
            continue
        fields = line.split('\t')
        if len(fields) < 4 or fields[3] in result:
            raise ValueError('HOMER inputs require unique explicit BED peak IDs')
        start, end = int(fields[1]), int(fields[2])
        if start < 0 or end <= start:
            raise ValueError('invalid BED coordinates')
        result[fields[3]] = dict(chrom=fields[0], start=start, end=end)
    return result


def normalize(raw, peaks, request):
    annotated, associations, seen = [], [], set()
    with Path(raw).open(newline='') as handle:
        reader = csv.DictReader(handle, delimiter='\t')
        if not reader.fieldnames or not reader.fieldnames[0].startswith('PeakID'):
            raise ValueError('HOMER output lacks PeakID header')
        for column in ('Annotation', 'Distance to TSS', 'Nearest PromoterID'):
            if column not in reader.fieldnames:
                raise ValueError(f'HOMER output lacks required column {column}')
        identifier_column = reader.fieldnames[0]
        for row in reader:
            identifier = row[identifier_column]
            if identifier in seen or identifier not in peaks:
                raise ValueError('duplicate or unknown HOMER peak ID')
            seen.add(identifier)
            gene = row['Nearest PromoterID'].strip()
            if gene in {'', 'NA', 'null', 'none', '-'}:
                gene = ''
            distance = row['Distance to TSS'].strip()
            if distance in {'', 'NA', 'null', 'none', '-'}:
                distance = ''
            elif not math.isfinite(float(distance)):
                raise ValueError('non-finite HOMER TSS distance')
            # This is a label projection only, never a genomic reannotation.
            native = row['Annotation']
            label = native.split(' (')[0].lower()
            category = {'promoter-tss':'promoter', 'tts':'tts', 'intergenic':'intergenic'}.get(label, label)
            identity = dict(peak_id=identifier, category=category, distance_to_tss=distance,
                            record_id=request.get('record_id') or '', source_id=request['source_id'],
                            annotation_provider='homer_4_11', association_method='homer_nearest_promoter',
                            homer_annotation=native)
            annotated.append({**identity, **peaks[identifier], 'gene_ids':gene, 'gene_count':int(bool(gene)), 'included':'true'})
            if gene:
                associations.append({**identity, 'gene_id':gene})
    if seen != set(peaks):
        raise ValueError('HOMER output does not cover the input peak IDs exactly')
    return annotated, associations


def attach_evidence(request, directories, peaks, annotated, associations, output):
    source = request.get('source_consensus')
    if not source:
        if directories:
            raise ValueError('unexpected consensus evidence without a declared source')
        return None
    if len(directories) != 1:
        raise ValueError('nfcore consensus annotation requires its explicit evidence bundle')
    root = Path(directories[0]).resolve()
    if sha(root / 'manifest.json') != request['inputs']['peak_manifest']['sha256']:
        raise ValueError('consensus evidence manifest differs from the validated source')
    required = ('regional_support', 'support_core', 'consolidated_peaks', 'source_peak_mapping', 'upstream_boolean')
    copied = output / 'consensus_evidence'
    copied.mkdir()
    files = {}
    if not set(required).issubset(source['artifacts']):
        raise ValueError('consensus source lacks required evidence artifacts')
    for role, artifact in source['artifacts'].items():
        name = artifact['path']
        path = (root / name).resolve()
        if Path(name).is_absolute() or root not in path.parents or not artifact.get('available'):
            raise ValueError('unsafe or unavailable consensus artifact')
        if sha(path) != artifact['sha256']:
            raise ValueError(f'consensus evidence checksum mismatch: {role}')
        target = copied / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        files[role] = target
    shutil.copy2(root / 'manifest.json', copied / 'manifest.json')
    support = defaultdict(list)
    seen = set()
    expected_records = set(request['record_ids'])
    if len(expected_records) != len(request['record_ids']) or not expected_records or any(not value for value in expected_records):
        raise ValueError('regional evidence requires unique nonempty library identities')
    with files['regional_support'].open(newline='') as handle:
        for row in csv.DictReader(handle, delimiter='\t'):
            identifier, record = row['peak_id'], row['record_id']
            if identifier not in peaks or record not in expected_records or (identifier, record) in seen:
                raise ValueError('invalid or duplicate regional support identity')
            seen.add((identifier, record))
            if row['occupancy_status'] != 'not_assessed':
                raise ValueError('regional support must not assert proven occupancy')
            covered, length, core = int(row['covered_bp']), int(row['region_bp']), int(row['region_core_bp'])
            fraction = float(row['covered_fraction'])
            calls = int(row['called_peak_count'])
            if calls < 0 or (calls > 0) != (covered > 0):
                raise ValueError('called peak count is inconsistent with covered bases')
            if length <= 0 or not 0 <= covered <= length or not 0 <= core <= length or not math.isfinite(fraction) or not 0 <= fraction <= 1:
                raise ValueError('invalid regional coverage evidence')
            if abs(fraction - covered / length) > 1e-6:
                raise ValueError('regional coverage fraction is inconsistent with covered bases')
            if row['classification'] not in {'candidate', 'candidate_with_library_support'}:
                raise ValueError('unsupported candidate classification')
            support[identifier].append(row)
    if len(seen) != len(peaks) * len(expected_records):
        raise ValueError('regional evidence must include every library, including zero support')
    summaries = {}
    for identifier, evidence in support.items():
        evidence.sort(key=lambda item: item['record_id'])
        calling = [item for item in evidence if int(item['called_peak_count']) > 0]
        count, total = len(calling), len(expected_records)
        classification = 'candidate_with_library_support' if count >= 2 else 'candidate'
        if not count or any(item['classification'] != classification for item in evidence):
            raise ValueError('candidate classification disagrees with calling libraries')
        if len({item['region_core_bp'] for item in evidence}) != 1:
            raise ValueError('inconsistent shared core across library evidence')
        summaries[identifier] = dict(
            calling_libraries=','.join(item['record_id'] for item in calling),
            calling_samples=','.join(item['sample_id'] for item in calling),
            calling_library_count=count, total_library_count=total,
            library_support_category=('single_library' if count == 1 else
                                      'all_libraries' if count == total else 'multiple_libraries'))
    for row in annotated + associations:
        evidence = sorted(support[row['peak_id']], key=lambda item: item['record_id'])
        row.update(library_support_json=json.dumps(evidence, sort_keys=True, separators=(',', ':')),
                   **summaries[row['peak_id']],
                   support_core_bp=evidence[0]['region_core_bp'], evidence_classification=evidence[0]['classification'],
                   occupancy_status='not_assessed')
    return dict(provider=source['provider'], strategy=source['strategy'], semantics=source['semantics'],
                libraries=len(expected_records), regions=len(peaks), occupancy_status='not_assessed',
                artifacts={role:dict(path='consensus_evidence/' + path.relative_to(copied).as_posix(), sha256=sha(path), available=True)
                           for role, path in files.items()})


def main():
    parser = argparse.ArgumentParser()
    for name in ('request','peaks','raw-dir','output-dir','manifest','execution','versions'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--support-dir', action='append', default=[])
    parser.add_argument('--cpus', type=int, default=1)
    parser.add_argument('--memory-bytes', type=int, default=0)
    parser.add_argument('--task-time', default='unknown')
    args = parser.parse_args()
    started = time.time()
    try:
        request = json.loads(Path(args.request).read_text())
        if request.get('status') != 'valid' or request.get('provider') != 'homer_4_11':
            raise ValueError('requires a validated homer_4_11 request')
        if sha(args.peaks) != request['inputs']['peaks']['sha256']:
            raise ValueError('peaks differ from validated request')
        raw = Path(args.raw_dir)
        package = json.loads((raw / 'homer.package.json').read_text())
        if package.get('name') != 'homer' or package.get('version') != '4.11':
            raise ValueError('HOMER package version mismatch')
        peaks = read_peaks(args.peaks)
        annotated, associations = normalize(raw / 'annotatePeaks.txt', peaks, request)
        output = Path(args.output_dir)
        output.mkdir(parents=True, exist_ok=False)
        shutil.copytree(raw, output / 'provider_reports')
        evidence = attach_evidence(request, args.support_dir, peaks, annotated, associations, output)
        common = ('peak_id','category','distance_to_tss','record_id','source_id','annotation_provider','association_method','homer_annotation')
        extra = ('calling_libraries','calling_samples','calling_library_count','total_library_count',
                 'library_support_category','support_core_bp','evidence_classification','occupancy_status','library_support_json') if evidence else ()
        write_table(output / 'annotated_peaks.tsv', common + ('chrom','start','end','gene_ids','gene_count','included') + extra, annotated)
        write_table(output / 'peak_gene_associations.tsv', common + ('gene_id',) + extra, associations)
        execution = dict(process='HOMER_ANNOTATION_ADAPTER', elapsed_seconds=time.time()-started,
                         cpus=args.cpus, memory_bytes=args.memory_bytes, time=args.task_time,
                         homer_execution=json.loads((raw / 'execution.json').read_text()) if (raw / 'execution.json').is_file() else None,
                         homer_package_build=package.get('build'), source_manifest_sha256=request['inputs']['peak_manifest']['sha256'])
        Path(args.execution).write_text(json.dumps(execution, indent=2) + '\n')
        Path(args.versions).write_text(f'"HOMER_ANNOTATION_ADAPTER":\n    homer: "4.11"\n    python: "{sys.version.split()[0]}"\n')
        artifacts = {role:dict(path=name, sha256=sha(output/name), available=True) for role,name in {
            'annotated_peaks':'annotated_peaks.tsv', 'peak_gene_associations':'peak_gene_associations.tsv',
            'homer_native':'provider_reports/annotatePeaks.txt'}.items()}
        manifest = {**{key:request.get(key) for key in ('id','source_id','source_type','record_id','record_ids','sample_ids',
                    'dataset','experiment_id','target','genome_id','build','organism','inputs','parameters')},
                    'schema_version':'1.0', 'type':'peak_annotation', 'provider':'homer_4_11', 'provider_version':'4.11',
                    'artifacts':artifacts, 'execution':execution, 'status':'complete' if annotated else 'complete_empty'}
        if evidence:
            manifest['consensus_evidence'] = evidence
        Path(args.manifest).write_text(json.dumps(manifest, indent=2) + '\n')
        shutil.copy2(args.manifest, output / 'manifest.json')
    except (ValueError, KeyError, OSError, json.JSONDecodeError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
