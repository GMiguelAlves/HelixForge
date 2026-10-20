#!/usr/bin/env python3
"""Orchestration adapter for the unchanged nf-core/chipseq 2.1.0 policy."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import time

UPSTREAM_COMMIT = '76e2382b6d443db4dc2396e6831d1243256d80b0'
HELPER_SHA256 = '71f9867dcec8ed1209df9d4e8772bb260b2057f62a95497dadea35779b19bcbe'


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def table(path, columns, rows):
    with Path(path).open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter='\t', lineterminator='\n', extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def run(request, directories, output, helper, cpus=1):
    if request.get('status') != 'valid' or request.get('strategy') != 'nfcore_2_1':
        raise ValueError('requires a validated nfcore_2_1 consensus request')
    if request.get('provider') != 'nfcore_chipseq_2.1.0':
        raise ValueError('incompatible provider identity')
    if sha(helper) != HELPER_SHA256:
        raise ValueError('upstream helper checksum mismatch')
    minimum = request['support_threshold']
    if isinstance(minimum, bool) or not isinstance(minimum, int) or not 1 <= minimum <= len(request['replicates']):
        raise ValueError('explicit min_replicates must be between 1 and library count')
    output.mkdir(parents=True, exist_ok=False)
    reports = output / 'provider_reports'
    reports.mkdir()
    commands = []

    def execute(command, destination=None):
        command = list(map(str, command))
        commands.append(command)
        with (reports / 'commands.txt').open('a') as log:
            log.write(shlex.join(command) + '\n')
        with (reports / 'tools.log').open('ab') as log:
            if destination is None:
                result = subprocess.run(command, stdout=subprocess.PIPE, stderr=log, check=False)
            else:
                with Path(destination).open('wb') as target:
                    result = subprocess.run(command, stdout=target, stderr=log, check=False)
        if result.returncode:
            raise ValueError(f'tool failed ({result.returncode}); see provider_reports/tools.log')
        return result.stdout.decode().strip() if destination is None else None

    version = execute(['bedtools', '--version'])
    if version != 'bedtools v2.30.0':
        raise ValueError(f'policy requires BEDTools 2.30.0, found {version}')
    source_index = {Path(path).name: Path(path) for path in directories}
    if len(source_index) != len(directories):
        raise ValueError('duplicate input directory basename')
    native, membership, identity, merged, original_peaks = [], [], {}, [], []
    narrow = request['peak_type'] == 'narrow'
    expected_columns = 10 if narrow else 9
    for index, replicate in enumerate(request['replicates'], 1):
        token = f'HF_REP{index:04d}'
        identity[token] = replicate
        source = source_index[replicate['peak_directory']] / replicate['peak_file']
        expected = replicate.get('peak_sha256')
        if not expected or sha(source) != expected:
            raise ValueError('input peak checksum differs from the validated request')
        normalized = reports / f'{token}_peaks.{"narrowPeak" if narrow else "broadPeak"}'
        with source.open() as handle, normalized.open('w') as target:
            for number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                fields = line.rstrip('\n').split('\t')
                if len(fields) != expected_columns:
                    raise ValueError('invalid MACS peak column count')
                original = fields[3]
                fields[3] = f'{token}_peak_{number}'
                membership.append(dict(upstream_name=fields[3], original_peak_name=original,
                    library_id=replicate['evidence_replicate_id'], record_id=replicate['record_id'], peak_id=replicate['peak_id']))
                target.write('\t'.join(fields) + '\n')
        native.append(normalized)
        sorted_path = reports / f'{token}.sorted.bed'
        execute(['sort', '-T', '.', '-k1,1', '-k2,2n', normalized], sorted_path)
        merged_path = reports / f'{token}.merged.bed'
        execute(['bedtools', 'merge', '-i', sorted_path], merged_path)
        # multiinter cannot accept empty files; empty libraries remain in the
        # regional support matrix and never acquire synthetic intervals.
        if merged_path.stat().st_size:
            merged.append((token, merged_path))
        original_peaks.append((token, sorted_path))
    table(output / 'source_peak_mapping.tsv', tuple(membership[0]) if membership else
          ('upstream_name', 'original_peak_name', 'library_id', 'record_id', 'peak_id'), membership)
    sorted_all = reports / 'all.sorted.peaks'
    execute(['sort', '-T', '.', '-k1,1', '-k2,2n', *native], sorted_all)
    collapsed = reports / 'merged.txt'
    columns = ','.join(map(str, range(2, expected_columns + 1)))
    execute(['bedtools', 'merge', '-i', sorted_all, '-c', columns,
             '-o', ','.join(['collapse'] * (expected_columns - 1))], collapsed)
    unfiltered = output / 'upstream.unfiltered.boolean.txt'
    boolean = output / 'upstream.boolean.txt'
    for destination, threshold in ((unfiltered, 1), (boolean, minimum)):
        command = [sys.executable, helper, collapsed, ','.join(identity), destination, '--min_replicates', str(threshold)]
        if narrow:
            command.append('--is_narrow_peak')
        execute(command)
    with unfiltered.open() as handle:
        unfiltered_rows = list(csv.DictReader(handle, delimiter='\t'))
    stable_ids = {(row['chr'], row['start'], row['end']): row['interval_id'] for row in unfiltered_rows}
    with (output / 'unfiltered_peaks.bed').open('w') as handle:
        for row in unfiltered_rows:
            handle.write(f"{row['chr']}\t{row['start']}\t{row['end']}\t{request['id']}.{row['interval_id']}\n")
    with boolean.open() as handle:
        rows = list(csv.DictReader(handle, delimiter='\t'))
    regions = []
    with (output / 'consolidated_peaks.bed').open('w') as bed, (output / 'upstream.bed').open('w') as raw:
        for row in rows:
            identifier = f"{request['id']}.{stable_ids[(row['chr'], row['start'], row['end'])]}"
            tokens = [token for token in identity if row[token + '.bool'] == 'TRUE']
            support = [identity[token]['evidence_replicate_id'] for token in tokens]
            region = dict(peak_id=identifier, chrom=row['chr'], start=int(row['start']), end=int(row['end']),
                          support=len(tokens), support_replicates=','.join(support),
                          classification='candidate_with_library_support' if len(tokens) >= 2 else 'candidate',
                          occupancy_status='not_assessed', upstream_interval_id=row['interval_id'])
            regions.append(region)
            bed.write(f"{row['chr']}\t{row['start']}\t{row['end']}\t{identifier}\n")
            raw.write(f"{row['chr']}\t{row['start']}\t{row['end']}\t{row['interval_id']}\t0\t+\n")
    table(output / 'consolidated_peaks.tsv', ('peak_id','chrom','start','end','support','support_replicates',
          'classification','occupancy_status','upstream_interval_id'), regions)
    retained = {(row['chrom'], str(row['start']), str(row['end'])) for row in regions}
    excluded = [dict(peak_id=f"{request['id']}.{row['interval_id']}", chrom=row['chr'], start=row['start'],
                     end=row['end'], calling_libraries=row['num_samples'], reason='below_min_replicates')
                for row in unfiltered_rows if (row['chr'], row['start'], row['end']) not in retained]
    table(output / 'excluded_regions.tsv', ('peak_id','chrom','start','end','calling_libraries','reason'), excluded)
    core_threshold = max(2, minimum)
    atomic = reports / 'atomic.tsv'
    core = output / 'support_core.bed'
    if len(merged) >= 2:
        execute(['bedtools', 'multiinter', '-i', *[p for _, p in merged], '-names', *[t for t, _ in merged]], atomic)
        with atomic.open() as handle, core.open('w') as target:
            for line in handle:
                fields = line.rstrip().split('\t')
                if int(fields[3]) >= core_threshold:
                    target.write('\t'.join(fields[:3]) + '\n')
    else:
        core.touch()
    core_coverage = reports / 'core.coverage.tsv'
    if regions:
        execute(['bedtools', 'coverage', '-a', output / 'consolidated_peaks.bed', '-b', core], core_coverage)
        core_bp = {fields[3]: int(fields[-3]) for fields in
                   (line.rstrip().split('\t') for line in core_coverage.open())}
    else:
        core_bp = {}
    supports = []
    classifications = {row['peak_id']: row['classification'] for row in regions}
    for token, peaks in original_peaks:
        replicate = identity[token]
        coverage = reports / f'{token}.coverage.tsv'
        if regions:
            execute(['bedtools', 'coverage', '-a', output / 'consolidated_peaks.bed', '-b', peaks], coverage)
            for fields in (line.rstrip().split('\t') for line in coverage.open()):
                supports.append(dict(peak_id=fields[3], library_id=replicate['evidence_replicate_id'],
                    record_id=replicate['record_id'], sample_id=replicate['sample_id'], source_peak_id=replicate['peak_id'],
                    called_peak_count=int(fields[-4]), covered_bp=int(fields[-3]), region_bp=int(fields[-2]),
                    covered_fraction=float(fields[-1]), region_core_bp=core_bp[fields[3]],
                    classification=classifications[fields[3]],
                    occupancy_status='not_assessed'))
    table(output / 'support_by_library.tsv', ('peak_id','library_id','record_id','sample_id','source_peak_id',
          'called_peak_count','covered_bp','region_bp','covered_fraction','region_core_bp','classification','occupancy_status'), supports)
    stats = dict(consolidated_peaks=len(regions), unfiltered_regions=len(unfiltered_rows), excluded_regions=len(excluded),
                 unfiltered_bp=sum(int(r['end'])-int(r['start']) for r in unfiltered_rows),
                 candidate_bp=sum(r['end']-r['start'] for r in regions),
                 core_min_libraries=core_threshold, regional_min_libraries=minimum,
                 candidate_with_library_support=sum(r['support'] >= 2 for r in regions),
                 core_bp=sum(int(line.split('\t')[2])-int(line.split('\t')[1]) for line in core.read_text().splitlines()))
    (output / 'statistics.json').write_text(json.dumps(stats, indent=2) + '\n')
    return stats, commands, version.removeprefix('bedtools v')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--request', required=True)
    parser.add_argument('--peak-dir', action='append', required=True)
    parser.add_argument('--helper', required=True)
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--execution', required=True)
    parser.add_argument('--versions', required=True)
    parser.add_argument('--cpus', type=int, default=1)
    parser.add_argument('--memory-bytes', type=int, default=0)
    parser.add_argument('--task-time', default='unknown')
    parser.add_argument('--environment', default='host')
    args = parser.parse_args()
    started = time.time()
    try:
        request = json.loads(Path(args.request).read_text())
        output = Path(args.output_dir)
        stats, commands, version = run(request, args.peak_dir, output, args.helper, args.cpus)
        status = 'complete' if stats['consolidated_peaks'] else 'complete_empty'
        execution = dict(process='NFCORE_CONSENSUS', commands=commands, cpus=args.cpus, memory_bytes=args.memory_bytes,
                         time=args.task_time, environment=args.environment, elapsed_seconds=time.time()-started,
                         upstream_commit=UPSTREAM_COMMIT, helper_sha256=sha(args.helper))
        Path(args.execution).write_text(json.dumps(execution, indent=2) + '\n')
        Path(args.versions).write_text(f'"NFCORE_CONSENSUS":\n    bedtools: "{version}"\n    nf_core_chipseq: "2.1.0"\n    python: "{sys.version.split()[0]}"\n')
        artifacts = {role: dict(available=True, path=name, sha256=sha(output / name)) for role, name in {
            'consolidated_bed':'consolidated_peaks.bed', 'consolidated_peaks':'consolidated_peaks.tsv',
            'regional_support':'support_by_library.tsv', 'support_core':'support_core.bed',
            'source_peak_mapping':'source_peak_mapping.tsv', 'upstream_boolean':'upstream.boolean.txt',
            'unfiltered_bed':'unfiltered_peaks.bed', 'unfiltered_boolean':'upstream.unfiltered.boolean.txt',
            'excluded_regions':'excluded_regions.tsv',
            'statistics':'statistics.json'}.items()}
        manifest = {**{key: request.get(key) for key in ('id','dataset','experiment_id','condition','treatment','target',
                    'genome_id','peak_type','caller','caller_version','replicate_mode','replicate_policy','replicates','parameters')},
            'schema_version':'1.0', 'type':'consensus', 'strategy':'nfcore_2_1', 'provider':'nfcore_chipseq_2.1.0',
            'provider_version':'2.1.0', 'upstream_commit':UPSTREAM_COMMIT, 'status':status, 'statistics':stats,
            'semantics':dict(consolidated_bed='merged_regional_candidates', support_core='atomic_shared_bases',
                             occupancy_status='not_assessed', merge_distance=0, bookended_intervals='merged'),
            'artifacts':artifacts, 'execution':execution}
        Path(args.manifest).write_text(json.dumps(manifest, indent=2) + '\n')
        shutil.copy2(args.manifest, output / 'manifest.json')
    except (ValueError, KeyError, OSError, json.JSONDecodeError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
