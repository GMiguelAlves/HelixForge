"""Small deterministic contract fixture, not a scientific benchmark."""
import argparse
import csv
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def generate(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=False)
    intervals = [[(100,400),(800,900),(900,1000)], [(350,600),(1200,1300)], [(590,750),(1600,1700)], []]
    records, directories, manifests, qc_manifests = [], [], [], []
    for index, regions in enumerate(intervals, 1):
        record_id = f'library_complex_name.{index}'
        directory = root / f'{record_id}.peaks'
        directory.mkdir()
        peaks = directory / 'peaks.broadPeak'
        peaks.write_text(''.join(f'chrFixture\t{start}\t{end}\told_name_with_underscores_{index}_{number}\t100\t.\t5\t10\t8\n'
                                for number, (start,end) in enumerate(regions, 1)))
        record = dict(group_id='fixture.H3K27me3', peak_id=f'{record_id}.macs3', peak_directory=directory.name,
                      record_id=record_id, sample_id=record_id, dataset='fixture', experiment_id='fixture.H3K27me3',
                      condition='adult', treatment='', target='H3K27me3', genome_id='fixture_v1', organism='fixture',
                      peak_type='broad', caller='macs3', caller_version='3.0.4', biological_replicate=str(index),
                      technical_replicate='1')
        identity = {**record, 'id':record['peak_id'], 'schema_version':'1.0', 'status':'complete'}
        manifest = root / f'{record_id}.peak.json'
        manifest.write_text(json.dumps({**identity, 'type':'peak_calling',
            'artifacts':{'peaks':dict(path='peaks.broadPeak', sha256=sha(peaks), available=True)}}) + '\n')
        qc = root / f'{record_id}.qc.json'
        qc.write_text(json.dumps({**identity, 'type':'peak_qc_frip'}) + '\n')
        records.append(record)
        directories.append(str(directory))
        manifests.append(str(manifest))
        qc_manifests.append(str(qc))
    with (root / 'plan.tsv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]), delimiter='\t', lineterminator='\n')
        writer.writeheader()
        writer.writerows(records)
    (root / 'records.json').write_text(json.dumps(records, indent=2) + '\n')
    fasta = root / 'reference.fa'
    fasta.write_text('>chrFixture\n' + 'ACGT' * 2000 + '\n')
    gtf = root / 'annotation.gtf'
    gtf.write_text(''.join(f'chrFixture\tfixture\t{feature}\t{start}\t{end}\t.\t{strand}\t.\tgene_id "{gene}"; transcript_id "{gene}.1";\n'
        for gene, strand, rows in [('gene_plus','+', [('gene',201,1800),('transcript',201,1800),('exon',201,450),('exon',1001,1800)]),
                                   ('gene_minus','-', [('gene',4001,7000),('transcript',4001,7000),('exon',4001,4500),('exon',6001,7000)])]
        for feature,start,end in rows))
    reference_doc = dict(schema_version='1.0', type='reference_bundle', id='fixture.reference', genome_id='fixture_v1',
        build='fixture_v1', organism='fixture', status='complete', artifacts={
            'reference':dict(path=fasta.name, sha256=sha(fasta), available=True),
            'annotation':dict(path=gtf.name, sha256=sha(gtf), available=True)})
    (root / 'reference.json').write_text(json.dumps(reference_doc, indent=2) + '\n')
    return records, directories, manifests, qc_manifests


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    generate(parser.parse_args().output)
