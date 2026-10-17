"""Tiny declared consensus/IDR inputs; no benchmark or biological data."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import subprocess


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def generate(root, real=False, status='complete'):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    def write_json(name, doc):
        path = root / name
        path.write_text(json.dumps(doc, indent=2) + '\n')
        return path
    reference = root / 'reference.fa'
    reference.write_text('>chrFixture\n' + 'ACGT' * 750 + '\n')
    annotation = root / 'annotation.gtf'
    annotation.write_text('chrFixture\tfixture\tgene\t201\t600\t.\t+\t.\tgene_id "g1";\n'
                          'chrFixture\tfixture\texon\t211\t250\t.\t+\t.\tgene_id "g1"; transcript_id "g1.t1";\n'
                          'chrFixture\tfixture\texon\t401\t450\t.\t+\t.\tgene_id "g1"; transcript_id "g1.t1";\n')
    write_json('reference.json', dict(schema_version='1.0', type='reference_bundle', id='fixture.reference',
               genome_id='fixture_v1', build='fixture_v1', organism='fixture', status=status,
               artifacts={role: dict(path=path.name, sha256=digest(path)) for role, path in [('reference', reference), ('annotation', annotation)]}))
    rows, records = [], []
    for identifier, control, replicate in [('input', True, '1'), ('ip1', False, '1'), ('ip2', False, '2')]:
        row = dict(record_id=identifier, sample_id=identifier, dataset='fixture', condition='treated',
                   target='Input' if control else 'H3K4me3', genome_id='fixture_v1', organism='fixture',
                   biological_replicate=replicate, technical_replicate='1', is_control=str(control).lower(),
                   control_id='' if control else 'input', layout='single', single_end='true')
        rows.append(row)
        bam, bai = root / f'{identifier}.bam', root / f'{identifier}.bam.bai'
        if real:
            sam = root / f'{identifier}.sam'
            sam.write_text('@HD\tVN:1.6\tSO:coordinate\n@SQ\tSN:chrFixture\tLN:3000\n' + ''.join(
                f'{identifier}.{i}\t0\tchrFixture\t{301 + i}\t60\t20M\t*\t0\t0\t' + ('ACGT' * 5) + '\t' + ('I' * 20) + '\n'
                for i in range(20)))
            subprocess.run(['samtools', 'view', '-b', '-o', str(bam), str(sam)], check=True)
            subprocess.run(['samtools', 'index', str(bam)], check=True)
        else:
            bam.write_bytes(b'contract-only placeholder; never a scientific BAM\n')
            bai.write_bytes(b'contract-only placeholder\n')
        write_json(f'{identifier}.json', dict(schema_version='1.0', type='bam_final', id=identifier,
                   **{key: row[key] for key in ('record_id', 'sample_id', 'dataset', 'condition', 'target', 'genome_id')},
                   artifact=bam.name, index=bai.name, sha256=digest(bam), index_sha256=digest(bai),
                   reference_sha256=digest(reference), status=status, duplicate_policy='none', blacklist_policy='none',
                   selection=dict(min_mapq=0, include_flags=0, exclude_flags=4)))
        records.append(dict(record_id=identifier, bam=bam.name, bai=bai.name, manifest=f'{identifier}.json'))
    metadata = root / 'metadata.tsv'
    with metadata.open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter='\t')
        writer.writeheader()
        writer.writerows(rows)
    write_json('metadata.json', dict(schema_version='1.0', type='chipseq_metadata', id='fixture.metadata',
               dataset='fixture', genome_id='fixture_v1', build='fixture_v1', status=status, rows=rows,
               artifacts={'metadata': dict(path=metadata.name, sha256=digest(metadata))}))
    peaks = root / 'peaks.bed'
    peaks.write_text('chrFixture\t290\t350\tp1\nchrFixture\t430\t460\tp2\n')
    for kind in ('consensus', 'idr'):
        provider = dict(schema_version='1.0', type=kind, id=f'fixture.{kind}', dataset='fixture', condition='treated',
                        target='H3K4me3', genome_id='fixture_v1', build='fixture_v1', organism='fixture', peak_type='narrow',
                        strategy='union' if kind == 'consensus' else 'idr', replicate_mode='biological',
                        replicate_policy='require_premerged', status=status,
                        replicates=[{key: row[key] for key in ('record_id', 'sample_id', 'condition', 'biological_replicate', 'technical_replicate')} for row in rows[1:]],
                        artifacts={'consolidated_bed': dict(path=peaks.name, sha256=digest(peaks))})
        write_json(f'{kind}.json', provider)
        inventory = dict(schema_version='1.0', type='chipseq_continuation_input', fixture_mode='real-tools' if real else 'contract-only',
                         project=dict(project_id='fixture', dataset='fixture', genome_id='fixture_v1', build='fixture_v1'),
                         metadata=dict(table=metadata.name, manifest='metadata.json'),
                         reference=dict(fasta=reference.name, annotation=annotation.name, manifest='reference.json'),
                         records=records, peaks=[dict(peaks=peaks.name, manifest=f'{kind}.json')], source_manifests=[])
        write_json(f'{kind}_input.json', inventory)
    return root


def indexed_request(root, kind='consensus'):
    doc = json.loads((Path(root) / f'{kind}_input.json').read_text())
    paths = []
    def register(value):
        path = Path(root) / value
        if path not in paths:
            paths.append(path)
        return paths.index(path)
    return dict(project=doc['project'], metadata={key: register(value) for key, value in doc['metadata'].items()},
                reference={key: register(value) for key, value in doc['reference'].items()},
                records=[dict(record_id=row['record_id'], **{key: register(row[key]) for key in ('bam', 'bai', 'manifest')}) for row in doc['records']],
                peaks=[{key: register(value) for key, value in row.items()} for row in doc['peaks']],
                source_manifests=[]), paths


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--outdir', type=Path, required=True)
    parser.add_argument('--real', action='store_true')
    args = parser.parse_args()
    generate(args.outdir, args.real, 'complete' if args.real else 'stub')
