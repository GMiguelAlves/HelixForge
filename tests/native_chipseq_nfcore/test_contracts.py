import base64
import csv
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from .generate_fixture import generate, sha

ROOT = Path(__file__).resolve().parents[2]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CONTEXT = load('nfcore_context', 'modules/local/consensus_context/resources/usr/bin/validate_consensus_context.py')
ANNOTATION = load('homer_context', 'modules/local/peak_annotation_context/resources/usr/bin/validate_peak_annotation_context.py')
ADAPTER = load('homer_adapter', 'modules/local/homer_annotation_adapter/resources/usr/bin/normalize_homer.py')
REPORT = load('nfcore_report', 'modules/local/report_aggregate/resources/usr/bin/report_aggregate.py')


class UpstreamTest(unittest.TestCase):
    def test_imported_sources_match_pinned_hashes(self):
        root = ROOT / 'vendor/nfcore_chipseq/2.1.0'
        pin = json.loads((root / 'upstream.json').read_text())
        self.assertEqual(pin['commit'], '76e2382b6d443db4dc2396e6831d1243256d80b0')
        self.assertEqual(pin['license'], 'MIT')
        for filename, declaration in pin['files'].items():
            with self.subTest(filename=filename):
                self.assertEqual(sha(root / filename), declaration['sha256'])

    def test_unmodified_helper_counts_libraries_not_peak_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            merged = root / 'merged.txt'
            merged.write_text('chr1\t0\t30\t0,10,20\t15,25,30\tHF_REP0001_peak_1,HF_REP0001_peak_2,HF_REP0002_peak_1\t1,1,1\t.,.,.\t5,6,7\t10,10,10\t8,8,8\n')
            output = root / 'table.txt'
            command = [sys.executable, str(ROOT / 'vendor/nfcore_chipseq/2.1.0/macs3_merged_expand.py'),
                       str(merged), 'HF_REP0001,HF_REP0002', str(output), '--min_replicates', '2']
            subprocess.run(command, check=True)
            with output.open() as handle:
                rows = list(csv.DictReader(handle, delimiter='\t'))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['num_peaks'], '3')
            self.assertEqual(rows[0]['num_samples'], '2')
            command[-1] = '3'
            subprocess.run(command, check=True)
            self.assertEqual(len(output.read_text().splitlines()), 1)


class ContextTest(unittest.TestCase):
    def test_homer_requires_gtf_ids_without_implicit_conversion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            generate(root/'fixture')
            ANNOTATION.validate_homer_gtf(root/'fixture/annotation.gtf')
            bad = root/'bad.gff'
            bad.write_text('chr1\tx\texon\t1\t10\t.\t+\t.\tID=exon1;Parent=tx1\n')
            with self.assertRaisesRegex(ValueError, 'not converted implicitly'):
                ANNOTATION.validate_homer_gtf(bad)

    def test_explicit_threshold_and_source_checksums(self):
        with tempfile.TemporaryDirectory() as tmp:
            records, directories, manifests, qc = generate(Path(tmp) / 'fixture')
            for minimum in (1, 2, 4):
                request = CONTEXT.build_request(records, directories, manifests, qc, {'strategy':'nfcore_2_1', 'min_replicates':minimum})
                self.assertEqual(request['provider'], 'nfcore_chipseq_2.1.0')
                self.assertEqual(request['support_threshold'], minimum)
                self.assertTrue(all(len(row['peak_sha256']) == 64 for row in request['replicates']))
            for minimum in (None, True, 0, 5, '2', 1.5):
                with self.subTest(minimum=minimum), self.assertRaisesRegex(ValueError, 'explicit integer'):
                    CONTEXT.build_request(records, directories, manifests, qc, {'strategy':'nfcore_2_1','min_replicates':minimum})

    def test_legacy_and_homer_parameters_cannot_be_conflated(self):
        self.assertEqual(ANNOTATION.validate_spec({})['provider'], 'python_interval_v1')
        with self.assertRaisesRegex(ValueError, 'explicit mode'):
            ANNOTATION.validate_spec({'provider':'homer_4_11'})
        with self.assertRaisesRegex(ValueError, 'compatibility parameter'):
            ANNOTATION.validate_spec({'provider':'homer_4_11','mode':'homer_native','promoter_upstream':100})
        spec = ANNOTATION.validate_spec({'provider':'homer_4_11','mode':'homer_native'})
        self.assertEqual(spec['arguments'], ['-gid'])
        self.assertNotIn('promoter_upstream', spec)

    def test_source_checksums_and_cross_group_identity_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            records, directories, manifests, qc = generate(Path(tmp)/'fixture')
            records[1]['condition'] = 'different'
            with self.assertRaisesRegex(ValueError, 'cross-talk'):
                CONTEXT.build_request(records, directories, manifests, qc, {'strategy':'nfcore_2_1','min_replicates':2})
            records[1]['condition'] = 'adult'
            source = Path(directories[0])/'peaks.broadPeak'
            source.write_text(source.read_text().replace('\t5\t','\t6\t',1))
            with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
                CONTEXT.build_request(records, directories, manifests, qc, {'strategy':'nfcore_2_1','min_replicates':2})


class HomerProjectionTest(unittest.TestCase):
    def evidence_fixture(self, root):
        bundle = root/'bundle'
        bundle.mkdir()
        output = root/'output'
        output.mkdir()
        columns = ['peak_id','library_id','record_id','sample_id','source_peak_id','called_peak_count',
                   'covered_bp','region_bp','covered_fraction','region_core_bp','classification','occupancy_status']
        rows = [dict(zip(columns, ['p1',str(i),f'r{i}',f's{i}',f'source{i}',str(count),str(bp),'10',str(bp/10),'0','candidate','not_assessed']))
                for i,count,bp in [(1,1,10),(2,0,0)]]
        support = bundle/'support.tsv'
        with support.open('w', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=columns, delimiter='\t', lineterminator='\n')
            writer.writeheader()
            writer.writerows(rows)
        files = {'regional_support':support}
        for role in ('support_core','consolidated_peaks','source_peak_mapping','upstream_boolean'):
            files[role] = bundle/(role+'.txt')
            files[role].write_text('fixture\n')
        source = dict(id='s',provider='nfcore_chipseq_2.1.0',strategy='nfcore_2_1',semantics={'occupancy_status':'not_assessed'},
                      artifacts={role:dict(path=path.name,sha256=sha(path),available=True) for role,path in files.items()})
        (bundle/'manifest.json').write_text(json.dumps(source))
        request = dict(source_consensus=source, record_ids=['r1','r2'], inputs={'peak_manifest':{'sha256':sha(bundle/'manifest.json')}})
        return bundle, output, request

    def test_evidence_keeps_zero_support_and_rejects_corruption(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle, output, request = self.evidence_fixture(Path(tmp))
            rows = [dict(peak_id='p1',gene_id='g')]
            result = ADAPTER.attach_evidence(request,[bundle],{'p1':{}},[],rows,output)
            evidence = json.loads(rows[0]['library_support_json'])
            self.assertEqual(len(evidence),2)
            self.assertEqual(evidence[1]['covered_bp'],'0')
            self.assertEqual(rows[0]['calling_libraries'],'r1')
            self.assertEqual(rows[0]['occupancy_status'],'not_assessed')
            self.assertEqual(result['libraries'],2)
        with tempfile.TemporaryDirectory() as tmp:
            bundle, output, request = self.evidence_fixture(Path(tmp))
            (bundle/'support.tsv').write_text('corrupted')
            with self.assertRaisesRegex(ValueError,'checksum mismatch'):
                ADAPTER.attach_evidence(request,[bundle],{'p1':{}},[],[],output)

    def test_missing_gene_and_native_feature_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            table = Path(tmp) / 'homer.txt'
            table.write_text('PeakID (command)\tAnnotation\tDistance to TSS\tNearest PromoterID\np1\tIntergenic\t-2500\tSmp_001\np2\tNA\tNA\tNA\n')
            peaks = dict(p1=dict(chrom='chr1',start=0,end=30), p2=dict(chrom='chr1',start=100,end=200))
            annotated, associations = ADAPTER.normalize(table, peaks, dict(source_id='source',record_id=None))
            self.assertEqual(len(associations), 1)
            self.assertEqual(associations[0]['gene_id'], 'Smp_001')
            self.assertEqual(associations[0]['category'], 'intergenic')
            self.assertEqual(annotated[0]['start'], 0)
            self.assertEqual(annotated[1]['gene_ids'], '')
            self.assertEqual(annotated[1]['distance_to_tss'], '')

    def test_unknown_duplicate_missing_and_nonfinite_results_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / 'homer.txt'
            peaks = dict(p1=dict(chrom='chr1', start=0, end=10))
            header = 'PeakID\tAnnotation\tDistance to TSS\tNearest PromoterID\n'
            cases = [header, header+'unknown\tintron\t1\tg\n', header+'p1\tintron\tnan\tg\n',
                     header+'p1\tintron\t1\tg\np1\tintron\t1\tg\n', 'PeakID\tUnexpected\n']
            for content in cases:
                raw.write_text(content)
                with self.subTest(content=content), self.assertRaises(ValueError):
                    ADAPTER.normalize(raw, peaks, {'source_id':'s'})

    def test_regional_annotation_requires_an_explicit_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            request = dict(source_consensus={'id':'s'})
            with self.assertRaisesRegex(ValueError, 'explicit evidence bundle'):
                ADAPTER.attach_evidence(request, [], {}, [], [], Path(tmp))

    def test_report_preserves_external_method_and_candidate_semantics(self):
        components = {name:{'status':'complete'} for name in ('metadata','reference','alignment','bam','peak','peak_qc','consensus_idr','differential_binding','annotation','tracks')}
        context = dict(project={'id':'fixture'}, id='report', components=components, status='complete')
        documents = [dict(type='peak_annotation_aggregate', id='ann', status='complete', annotation_providers=['homer_4_11'],
                          consensus_evidence=[{'occupancy_status':'not_assessed', 'strategy':'nfcore_2_1'}])]
        data = REPORT.aggregate(context, documents, [])['sections']['annotation']['data']
        self.assertIn('not establish confirmed occupancy', data['interpretation'])
        self.assertEqual(data['manifests'][0]['consensus_evidence'][0]['occupancy_status'],'not_assessed')


if __name__ == '__main__':
    unittest.main()
