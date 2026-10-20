"""Compare the HF fixture with direct pinned-tool commands, independently."""
import argparse
import csv
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
CONSENSUS_IMAGE = 'quay.io/biocontainers/mulled-v2-2f48cc59b03027e31ead6d383fe1b8057785dd24:5d182f583f4696f4c4d9f3be93052811b383341f-0@sha256:2bb8995555bc3505389b8534063f1743c9f31dd3055a3b559b8c4f077a9add53'
HOMER_IMAGE = 'quay.io/biocontainers/homer:4.11--pl526hc9558a2_3@sha256:69628c89cf46a36838a0bdc2b6c76fba1587d994d07437440636f26d0320b447'


def locate(root, pattern):
    found = list(root.glob(pattern))
    if len(found) != 1:
        raise AssertionError(f'expected exactly one {pattern}, got {len(found)}')
    return found[0]


def validate(fixture, results, output):
    output.mkdir(parents=True, exist_ok=False)
    consensus = locate(results, 'chipseq/consensus/*/*.consensus_result')
    provider = locate(results, 'chipseq/peak_annotation/*.peak_annotation')
    records = json.loads((fixture / 'records.json').read_text())
    tokens = []
    for number, record in enumerate(records, 1):
        token = f'HF_REP{number:04d}'
        tokens.append(token)
        source = fixture / record['peak_directory'] / 'peaks.broadPeak'
        with (output / f'{token}_peaks.broadPeak').open('w') as handle:
            for index, line in enumerate(source.read_text().splitlines(), 1):
                columns = line.split('\t')
                columns[3] = f'{token}_peak_{index}'
                handle.write('\t'.join(columns) + '\n')

    def docker(image, script, log_name):
        command = ['docker','run','--rm','--entrypoint','/bin/bash',
                   '-v',f'{ROOT}:/repo:ro','-v',f'{fixture}:/fixture:ro',
                   '-v',f'{results}:/results:ro','-v',f'{output}:/direct','-w','/direct',image,'-lc',script]
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        (output / log_name).write_text(result.stdout)
        if result.returncode:
            raise AssertionError(f'direct tool execution failed: {log_name}')

    docker(CONSENSUS_IMAGE, f'''set -euo pipefail
export LC_ALL=C
sort -T . -k1,1 -k2,2n HF_REP*_peaks.broadPeak | mergeBed -c 2,3,4,5,6,7,8,9 -o collapse,collapse,collapse,collapse,collapse,collapse,collapse,collapse > merged.txt
python3 /repo/vendor/nfcore_chipseq/2.1.0/macs3_merged_expand.py merged.txt {','.join(tokens)} unfiltered.txt --min_replicates 1
python3 /repo/vendor/nfcore_chipseq/2.1.0/macs3_merged_expand.py merged.txt {','.join(tokens)} filtered.txt --min_replicates 2
python3 /repo/vendor/nfcore_chipseq/2.1.0/macs3_merged_expand.py merged.txt {','.join(tokens)} empty.txt --min_replicates 4
''', 'direct-consensus.log')
    assert (output/'unfiltered.txt').read_bytes() == (consensus/'upstream.unfiltered.boolean.txt').read_bytes(), 'unfiltered consensus differs'
    assert (output/'filtered.txt').read_bytes() == (consensus/'upstream.boolean.txt').read_bytes(), 'filtered consensus differs'
    with (output/'empty.txt').open() as handle:
        assert list(csv.DictReader(handle, delimiter='\t')) == [], 'four-library threshold should reject every region'
    document = json.loads((consensus/'manifest.json').read_text())
    assert document['status'] == 'complete'
    statistics = document['statistics']
    assert (statistics['unfiltered_regions'],statistics['excluded_regions'],statistics['consolidated_peaks']) == (4,3,1)
    assert statistics['unfiltered_bp'] == 1050 and statistics['candidate_bp'] == 650
    assert statistics['core_bp'] == 60, 'core should not trim the 650 bp regional candidate'
    columns = (consensus/'consolidated_peaks.bed').read_text().strip().split('\t')
    assert (int(columns[1]),int(columns[2])) == (100,750)
    support = list(csv.DictReader((consensus/'support_by_library.tsv').open(), delimiter='\t'))
    assert len(support) == 4 and sum(int(row['covered_bp']) == 0 for row in support) == 1

    relative = (consensus/'consolidated_peaks.bed').relative_to(results).as_posix()
    docker(HOMER_IMAGE, f'''set -euo pipefail
annotatePeaks.pl '/results/{relative}' /fixture/reference.fa -gid -gtf /fixture/annotation.gtf -cpu 1 > annotatePeaks.txt
''', 'direct-homer.log')
    with (output/'annotatePeaks.txt').open() as handle:
        direct = list(csv.reader(handle, delimiter='\t'))
    with (provider/'provider_reports/annotatePeaks.txt').open() as handle:
        native = list(csv.reader(handle, delimiter='\t'))
    assert direct[0][1:] == native[0][1:] and direct[1:] == native[1:], 'HOMER output differs beyond command header'
    projected = list(csv.DictReader((provider/'peak_gene_associations.tsv').open(), delimiter='\t'))
    assert len(projected) == 1 and projected[0]['gene_id'] == 'gene_plus', 'GTF gene_id not preserved'
    evidence = json.loads(projected[0]['library_support_json'])
    assert {row['record_id'] for row in evidence} == {row['record_id'] for row in records}
    assert projected[0]['support_core_bp'] == '60'
    assert projected[0]['evidence_classification'] == 'candidate_with_library_support'
    assert projected[0]['occupancy_status'] == 'not_assessed'
    aggregate = results/'chipseq/peak_annotation/peak_annotation_aggregate/peak_gene_associations.tsv'
    rows = list(csv.DictReader(aggregate.open(), delimiter='\t'))
    assert rows[0]['library_support_json'] == projected[0]['library_support_json'], 'aggregation dropped library evidence'
    doc = dict(status='PASS', benchmark=False, scope='reduced_tool_equivalence',
               checks=['upstream_unfiltered_exact','upstream_filtered_exact','support_exclusions',
                       'zero_support_library','unclipped_catalog','homer_direct_equivalence','gtf_gene_id',
                       'association_evidence','aggregate_evidence'],
               unfiltered_regions=4, retained_regions=1, unfiltered_bp=1050, retained_bp=650, core_bp=60)
    (output/'validation.json').write_text(json.dumps(doc, indent=2) + '\n')
    print(json.dumps(doc))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for argument in ('fixture','results','output'):
        parser.add_argument('--'+argument, required=True, type=Path)
    args = parser.parse_args()
    validate(args.fixture.resolve(), args.results.resolve(), args.output.resolve())
