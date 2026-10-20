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
from .validate_real import compare_homer_tables

ROOT = Path(__file__).resolve().parents[2]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CONTEXT = load('nfcore_context', 'modules/local/consensus_context/resources/usr/bin/validate_consensus_context.py')
ANNOTATION = load('homer_context', 'modules/local/peak_annotation_context/resources/usr/bin/validate_peak_annotation_context.py')
ADAPTER = load('homer_adapter', 'modules/local/homer_annotation_adapter/resources/usr/bin/normalize_homer.py')
CONSENSUS = load('nfcore_provider', 'modules/local/nfcore_consensus/resources/usr/bin/nfcore_consensus.py')
REPORT = load('nfcore_report', 'modules/local/report_aggregate/resources/usr/bin/report_aggregate.py')
AGGREGATE = load('nfcore_annotation_aggregate', 'modules/local/peak_annotation_aggregate/resources/usr/bin/peak_annotation_aggregate.py')


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
            default = CONTEXT.build_request(records, directories, manifests, qc, {'strategy':'nfcore_2_1'})
            self.assertEqual(default['support_threshold'], 1)
            self.assertEqual(default['parameters']['min_replicates'], 1)
            self.assertEqual(CONTEXT.build_request(records, directories, manifests, qc,
                             {'strategy':'nfcore_2_1', 'min_replicates':None})['support_threshold'], 1)
            with self.assertRaisesRegex(ValueError, 'explicit integer'):
                CONTEXT.build_request(records, directories, manifests, qc, {'strategy':'replicate_support'})
            for minimum in (True, 0, 5, '2', 1.5):
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
    def test_ambiguity_flags_tied_genes_without_reassigning_homer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw,tss = root/'homer.txt',root/'tss.tsv'
            tss.write_text('g1\tchr1\t-1800\t2200\t+\t0\ng2\tchr1\t-1800\t2200\t-\t0\n'
                           'g2\tchr1\t-1800\t2200\t-\t0\nother\tchr2\t-1800\t2200\t+\t0\n')
            for selected,alternative in [('g1','g2'),('g2','g1')]:
                raw.write_text('PeakID\tChr\tStart\tEnd\tAnnotation\tDistance to TSS\tNearest PromoterID\n'
                               f'p1\tchr1\t290\t310\tintron\t100\t{selected}\n')
                annotated,associations = ADAPTER.normalize(raw,{'p1':dict(chrom='chr1',start=289,end=310)},{'source_id':'s'})
                summary = ADAPTER.assess_ambiguity(raw,tss,annotated,associations)
                for row in annotated+associations:
                    self.assertEqual(row['gene_assignment_ambiguous'],'true')
                    self.assertEqual(row['gene_assignment_ambiguity_reason'],'nearest_tss_distance_tie')
                    self.assertEqual(json.loads(row['alternative_gene_ids']),[alternative])
                    self.assertEqual(row['distance_to_tss'],'100')
                self.assertEqual(associations[0]['gene_id'],selected)
                self.assertEqual(annotated[0]['gene_ids'],selected)
                self.assertEqual(annotated[0]['gene_count'],1)
                self.assertEqual(summary['counts'],{'true':1,'false':0,'not_assessed':0})

    def test_ambiguity_checks_equidistant_positions_and_distinct_genes(self):
        cases = [('g1\tchr1\t-1800\t2200\t+\t0\ng2\tchr1\t-1600\t2400\t+\t0\n','true'),
                 ('g1\tchr1\t-1800\t2200\t+\t0\ng1\tchr1\t-1600\t2400\t+\t0\n','false'),
                 ('g1\tchr1\t-1800\t2200\t+\t0\ng2\tchr2\t-1800\t2200\t+\t0\n','false'),
                 ('g1\tchr1\t-1800\t2200\t+\t0\ng2\tchr1\t-1720\t2280\t+\t0\n','not_assessed')]
        for snapshot,flag in cases:
            with self.subTest(flag=flag,snapshot=snapshot), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                raw,tss = root/'homer.txt',root/'tss.tsv'
                raw.write_text('PeakID\tChr\tStart\tEnd\n'+'p1\tchr1\t290\t310\n')
                tss.write_text(snapshot)
                rows = [dict(peak_id='p1',gene_ids='g1',distance_to_tss='100')]
                ADAPTER.assess_ambiguity(raw,tss,rows,[])
                self.assertEqual(rows[0]['gene_assignment_ambiguous'],flag)

    def test_ambiguity_is_not_assessed_without_required_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw,tss = root/'homer.txt',root/'tss.tsv'
            raw.write_text('PeakID\n'+'p1\n')
            tss.write_text('g1\tchr1\t-1800\t2200\t+\t0\n')
            for snapshot,gene in [(None,'g1'),(tss,'g1'),(tss,''),(tss,'unknown')]:
                rows = [dict(peak_id='p1',gene_ids=gene,distance_to_tss='100')]
                ADAPTER.assess_ambiguity(raw,snapshot,rows,[])
                self.assertEqual(rows[0]['gene_assignment_ambiguous'],'not_assessed')
                self.assertEqual(rows[0]['alternative_gene_ids'],'[]')
            tss.write_text('g1\tchr1\t0\t100\t+\t0\n')
            with self.assertRaisesRegex(ValueError,'TSS window'):
                ADAPTER.assess_ambiguity(raw,tss,rows,[])

    def test_adapter_validates_snapshot_provenance_and_publishes_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = root/'raw'
            raw.mkdir()
            (raw/'homer.package.json').write_text(json.dumps(dict(name='homer',version='4.11')))
            (raw/'annotatePeaks.txt').write_text('PeakID\tChr\tStart\tEnd\tAnnotation\tDistance to TSS\tNearest PromoterID\n'
                                               'p1\tchr1\t290\t310\tintron\t100\tg1\n')
            peaks = root/'peaks.bed'
            peaks.write_text('chr1\t289\t310\tp1\n')
            tss = raw/'reference_tss.tsv'
            tss.write_text('g1\tchr1\t-1800\t2200\t+\t0\ng2\tchr1\t-1800\t2200\t+\t0\n')
            request = root/'request.json'
            request.write_text(json.dumps(dict(status='valid',provider='homer_4_11',id='annotation',source_id='source',
                               inputs=dict(peaks=dict(sha256=sha(peaks)),annotation=dict(sha256='a'*64),
                                           peak_manifest=dict(sha256='c'*64)))))
            for mode in ('valid','bad_tss_checksum','wrong_annotation'):
                metadata = dict(provider='homer_4_11',annotation_sha256='a'*64,tss_sha256=sha(tss))
                if mode == 'bad_tss_checksum':
                    metadata['tss_sha256'] = '0'*64
                if mode == 'wrong_annotation':
                    metadata['annotation_sha256'] = 'b'*64
                (raw/'reference_tss.metadata.json').write_text(json.dumps(metadata))
                output = root/mode
                command = [sys.executable,str(ROOT/'modules/local/homer_annotation_adapter/resources/usr/bin/normalize_homer.py'),
                           '--request',str(request),'--peaks',str(peaks),'--raw-dir',str(raw),'--output-dir',str(output),
                           '--manifest',str(root/(mode+'.json')),'--execution',str(root/(mode+'.execution.json')),
                           '--versions',str(root/(mode+'.yml'))]
                result = subprocess.run(command,capture_output=True,text=True)
                if mode != 'valid':
                    self.assertEqual(result.returncode,2)
                    self.assertIn('snapshot checksum or annotation mismatch',result.stderr)
                    self.assertFalse(output.exists())
                    continue
                self.assertEqual(result.returncode,0,result.stderr)
                with (output/'peak_gene_associations.tsv').open() as handle:
                    rows = list(csv.DictReader(handle,delimiter='\t'))
                self.assertEqual(len(rows),1)
                self.assertEqual(rows[0]['gene_id'],'g1')
                self.assertEqual(rows[0]['gene_assignment_ambiguous'],'true')
                self.assertEqual(json.loads(rows[0]['alternative_gene_ids']),['g2'])
                manifest = json.loads((output/'manifest.json').read_text())
                self.assertEqual(manifest['gene_assignment_ambiguity']['counts']['true'],1)
                self.assertEqual(manifest['artifacts']['annotation_tss']['sha256'],sha(tss))

    def test_direct_comparison_uses_ids_without_hiding_annotation_changes(self):
        direct = [['PeakID (direct)','Nearest PromoterID'],['p1','g1'],['p2','g2']]
        native = [['PeakID (native)','Nearest PromoterID'],['p2','g2'],['p1','g1']]
        compare_homer_tables(direct,native)
        for rows in [[['p1','other_gene'],['p2','g2']], [['p1','g1']],
                     [['p1','g1'],['p1','g1'],['p2','g2']]]:
            with self.subTest(rows=rows), self.assertRaises(AssertionError):
                compare_homer_tables(direct,[native[0],*rows])

    def evidence_fixture(self, root, callers=1, total=2):
        bundle = root/'bundle'
        bundle.mkdir()
        output = root/'output'
        output.mkdir()
        columns = ['peak_id','library_id','record_id','sample_id','source_peak_id','called_peak_count',
                   'covered_bp','region_bp','covered_fraction','region_core_bp','classification','occupancy_status']
        classification = 'candidate' if callers == 1 else 'candidate_with_library_support'
        rows = [dict(zip(columns, ['p1',str(i),f'r{i}',f's{i}',f'source{i}',str(int(i <= callers)),
                                   str(10 if i <= callers else 0),'10',str(int(i <= callers)),
                                   '0',classification,'not_assessed'])) for i in range(1,total+1)]
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
        request = dict(source_consensus=source, record_ids=[f'r{i}' for i in range(1,total+1)], inputs={'peak_manifest':{'sha256':sha(bundle/'manifest.json')}})
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
            self.assertEqual(rows[0]['calling_samples'],'s1')
            self.assertEqual(rows[0]['calling_library_count'],1)
            self.assertEqual(rows[0]['total_library_count'],2)
            self.assertEqual(rows[0]['library_support_category'],'single_library')
            self.assertEqual(rows[0]['occupancy_status'],'not_assessed')
            self.assertEqual(result['libraries'],2)
        with tempfile.TemporaryDirectory() as tmp:
            bundle, output, request = self.evidence_fixture(Path(tmp))
            (bundle/'support.tsv').write_text('corrupted')
            with self.assertRaisesRegex(ValueError,'checksum mismatch'):
                ADAPTER.attach_evidence(request,[bundle],{'p1':{}},[],[],output)

    def test_library_categories_agree_in_catalog_and_gene_associations(self):
        for callers,total,category in [(1,3,'single_library'),(2,3,'multiple_libraries'),
                                        (3,3,'all_libraries'),(2,2,'all_libraries')]:
            with self.subTest(callers=callers,total=total), tempfile.TemporaryDirectory() as tmp:
                bundle,output,request = self.evidence_fixture(Path(tmp),callers,total)
                annotated,associations = [dict(peak_id='p1')],[dict(peak_id='p1',gene_id='g')]
                ADAPTER.attach_evidence(request,[bundle],{'p1':{}},annotated,associations,output)
                summary = CONSENSUS.library_summary([
                    dict(record_id=f'r{i}',sample_id=f's{i}') for i in reversed(range(1,callers+1))],total)
                self.assertEqual(summary['library_support_category'],category)
                self.assertEqual(summary['calling_libraries'],','.join(f'r{i}' for i in range(1,callers+1)))
                for row in annotated+associations:
                    for key,value in summary.items():
                        self.assertEqual(row[key],value)
                    self.assertEqual(len(json.loads(row['library_support_json'])),total)

    def test_invalid_evidence_fails_even_with_updated_checksums(self):
        cases = [('missing_library',lambda rows: rows.pop()),
                 ('duplicate_library',lambda rows: rows.append(dict(rows[0]))),
                 ('wrong_class',lambda rows: rows[0].update(classification='candidate_with_library_support')),
                 ('negative_calls',lambda rows: rows[1].update(called_peak_count='-1')),
                 ('false_presence',lambda rows: rows[1].update(called_peak_count='1')),
                 ('wrong_core',lambda rows: rows[1].update(region_core_bp='1'))]
        for name,mutate in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                bundle,output,request = self.evidence_fixture(Path(tmp))
                path = bundle/'support.tsv'
                with path.open(newline='') as handle:
                    reader = csv.DictReader(handle,delimiter='\t')
                    columns,rows = reader.fieldnames,list(reader)
                mutate(rows)
                ADAPTER.write_table(path,columns,rows)
                request['source_consensus']['artifacts']['regional_support']['sha256'] = sha(path)
                (bundle/'manifest.json').write_text(json.dumps(request['source_consensus']))
                request['inputs']['peak_manifest']['sha256'] = sha(bundle/'manifest.json')
                with self.assertRaises(ValueError):
                    ADAPTER.attach_evidence(request,[bundle],{'p1':{}},[],[],output)

    def test_empty_annotation_preserves_zero_region_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle,output,request = self.evidence_fixture(Path(tmp))
            path = bundle/'support.tsv'
            path.write_text(path.read_text().splitlines()[0]+'\n')
            request['source_consensus']['artifacts']['regional_support']['sha256'] = sha(path)
            (bundle/'manifest.json').write_text(json.dumps(request['source_consensus']))
            request['inputs']['peak_manifest']['sha256'] = sha(bundle/'manifest.json')
            result = ADAPTER.attach_evidence(request,[bundle],{},[],[],output)
            self.assertEqual(result['regions'],0)
            self.assertEqual(result['libraries'],2)

    def test_empty_tsv_preserves_library_contract_headers(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'empty.tsv'
            columns = ['peak_id', *CONSENSUS.LIBRARY_COLUMNS]
            ADAPTER.write_table(path,columns,[])
            found = set()
            self.assertEqual(AGGREGATE.read_rows(path,found),[])
            self.assertEqual(found,set(columns))

    def test_catalog_rejects_impossible_support_counts(self):
        for calling,total in [([],3),([dict(record_id='r1',sample_id='s1')],0)]:
            with self.subTest(total=total), self.assertRaises(ValueError):
                CONSENSUS.library_summary(calling,total)

    def test_catalog_rejects_ambiguous_source_library_ids_before_tools(self):
        for identifiers in [('same','same'),('','r2'),('r1,r2','r3'),('r1\tr2','r3')]:
            with self.subTest(identifiers=identifiers), tempfile.TemporaryDirectory() as tmp:
                request = dict(status='valid',strategy='nfcore_2_1',provider='nfcore_chipseq_2.1.0',
                               support_threshold=1,replicates=[dict(record_id=value) for value in identifiers])
                with self.assertRaisesRegex(ValueError,'library record IDs'):
                    CONSENSUS.run(request,[],Path(tmp)/'output',ROOT/'vendor/nfcore_chipseq/2.1.0/macs3_merged_expand.py')

    def test_aggregate_preserves_mixed_and_empty_library_columns(self):
        for empty in (False,True):
            with self.subTest(empty=empty), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                command = [sys.executable,str(ROOT/'modules/local/peak_annotation_aggregate/resources/usr/bin/peak_annotation_aggregate.py')]
                for identifier,regional in [('regional',True),('compatibility',False)]:
                    directory = root/identifier
                    directory.mkdir()
                    doc = dict(id=identifier,type='peak_annotation',source_id=identifier,status='complete_empty' if empty else 'complete',
                               provider='homer_4_11' if regional else 'python_interval_v1')
                    (directory/'manifest.json').write_text(json.dumps(doc))
                    rows = [] if empty else [dict(peak_id=identifier,gene_id='g',**(
                        CONSENSUS.library_summary([dict(record_id='r1',sample_id='s1')],2) if regional else {}))]
                    if regional and rows:
                        rows[0].update(gene_assignment_ambiguous='true',gene_assignment_ambiguity_reason='nearest_tss_distance_tie',
                                       gene_assignment_ambiguity_scope=ADAPTER.AMBIGUITY_SCOPE,alternative_gene_ids='["g2"]')
                    columns = ['peak_id','gene_id',*(CONSENSUS.LIBRARY_COLUMNS + ADAPTER.AMBIGUITY_COLUMNS if regional else ())]
                    for name in ('annotated_peaks.tsv','peak_gene_associations.tsv'):
                        ADAPTER.write_table(directory/name,columns,rows)
                    stats = dict(id=identifier,total_peaks=len(rows),annotated_peaks=len(rows),unassociated_peaks=0,
                                 unique_genes=len(rows),mean_genes_per_peak=1 if rows else 0,status=doc['status'])
                    stats_path,stats_manifest = root/(identifier+'.stats.json'),root/(identifier+'.stats_manifest.json')
                    stats_path.write_text(json.dumps(stats))
                    stats_manifest.write_text(json.dumps(dict(id=identifier,type='peak_annotation_statistics')))
                    command += ['--annotation-dir',str(directory),'--annotation-manifest',str(directory/'manifest.json'),
                                '--statistics-json',str(stats_path),'--statistics-manifest',str(stats_manifest)]
                command += ['--output-dir',str(root/'aggregate'),'--manifest',str(root/'manifest.json'),
                            '--execution',str(root/'execution.json'),'--versions',str(root/'versions.yml'),
                            '--cpus','1','--memory-bytes','1000','--task-time','1m']
                subprocess.run(command,check=True,capture_output=True,text=True)
                for name in ('annotated_peaks.tsv','peak_gene_associations.tsv'):
                    with (root/'aggregate'/name).open() as handle:
                        reader = csv.DictReader(handle,delimiter='\t')
                        self.assertTrue(set(CONSENSUS.LIBRARY_COLUMNS).issubset(reader.fieldnames))
                        self.assertTrue(set(ADAPTER.AMBIGUITY_COLUMNS).issubset(reader.fieldnames))
                        result = {row['peak_id']:row for row in reader}
                    if empty:
                        self.assertEqual(result,{})
                    else:
                        self.assertEqual(result['regional']['calling_libraries'],'r1')
                        self.assertEqual(result['regional']['library_support_category'],'single_library')
                        self.assertEqual(result['regional']['gene_assignment_ambiguous'],'true')
                        self.assertEqual(json.loads(result['regional']['alternative_gene_ids']),['g2'])
                        self.assertEqual(result['compatibility']['gene_assignment_ambiguous'],'')
                        for key in CONSENSUS.LIBRARY_COLUMNS:
                            self.assertEqual(result['compatibility'][key],'')

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
