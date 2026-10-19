import importlib.util
import json
from pathlib import Path
import random
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


def load(name,path):
    spec = importlib.util.spec_from_file_location(name,path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


P = load('regional_provider',ROOT/'modules/local/regional_catalog/resources/usr/bin/run_regional_catalog.py')
C = load('regional_context',ROOT/'modules/local/consensus_context/resources/usr/bin/validate_consensus_context.py')
A = load('regional_aggregate',ROOT/'modules/local/consensus_aggregate/resources/usr/bin/consensus_aggregate.py')


class RegionalCatalogTests(unittest.TestCase):
    def test_one_base_core_does_not_replace_full_region(self):
        rows,matrix,core = P.consolidate([('c',0,199,('A',)),('c',199,200,('A','B')),('c',200,400,('B',))],['A','B'],2,'g')
        self.assertEqual([(r['start'],r['end']) for r in rows],[(0,400)])
        self.assertEqual(rows[0]['core_bp'],1)
        self.assertEqual(rows[0]['below_threshold_bp'],399)
        self.assertEqual(rows[0]['occupancy_status'],'not_assessed')
        self.assertEqual(rows[0]['classification'],'spatially_supported_candidate')
        self.assertEqual([(r[1],r[2]) for r in core],[(199,200)])
        self.assertEqual([r['called_bp'] for r in matrix],[200,201])

    def test_bookending_different_libraries_is_not_replicated_support(self):
        rows,matrix,core = P.consolidate([('c',0,10,('A',)),('c',10,20,('B',))],['A','B'],2,'g')
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['support'],2)
        self.assertEqual(rows[0]['classification'],'candidate')
        self.assertEqual(core,[])

    def test_no_positive_gap_filling(self):
        rows,_,_ = P.consolidate([('c',0,10,('A',)),('c',11,20,('B',))],['A','B'],2,'g')
        self.assertEqual([(r['start'],r['end']) for r in rows],[(0,10),(11,20)])

    def test_missing_unit_has_explicit_zero(self):
        _,matrix,_ = P.consolidate([('c',0,10,('A',))],['A','B'],2,'g')
        self.assertEqual(matrix[1]['called_bp'],0)
        self.assertEqual(matrix[1]['has_call'],'false')

    def test_empty_is_a_valid_empty_catalog_not_fallback(self):
        self.assertEqual(P.consolidate([],['A','B'],2,'g'),([],[],[]))

    def test_chromosomes_never_join(self):
        rows,_,_ = P.consolidate([('a',0,10,('A','B')),('b',10,20,('A','B'))],['A','B'],2,'g')
        self.assertEqual(len(rows),2)

    def test_three_unit_threshold_preserves_partial_support(self):
        rows,_,core = P.consolidate([('c',0,5,('A','B')),('c',5,10,('A','B','C'))],['A','B','C'],3,'g')
        self.assertEqual(rows[0]['core_bp'],5)
        self.assertEqual(core[0][1:3],(5,10))
        # A chain touching three units is not three-unit co-occupancy.
        chain = [('c',0,90,('A',)),('c',90,100,('A','B')),('c',100,110,('B','C')),('c',110,200,('C',))]
        rows,_,core = P.consolidate(chain,['A','B','C'],3,'g')
        self.assertEqual(rows[0]['support'],3)
        self.assertEqual(rows[0]['classification'],'candidate')
        self.assertEqual(core,[])

    def test_unit_coverage_and_core_match_independent_per_base_truth(self):
        rng = random.Random(53)
        for _ in range(100):
            per_base = [tuple(unit for unit in ('A','B','C') if rng.random()<.55) for _ in range(70)]
            atoms = [('c',i,i+1,units) for i,units in enumerate(per_base) if units]
            rows,matrix,core = P.consolidate(atoms,['A','B','C'],2,'g')
            actual = {i for r in rows for i in range(r['start'],r['end'])}
            expected = {i for i,u in enumerate(per_base) if u}
            self.assertEqual(actual,expected)
            self.assertEqual({i for c,a,b,_ in core for i in range(a,b)}, {i for i,u in enumerate(per_base) if len(u)>=2})
            for r in rows:
                for m in [v for v in matrix if v['peak_id']==r['peak_id']]:
                    self.assertEqual(m['called_bp'],sum(m['replicate_id'] in per_base[i] for i in range(r['start'],r['end'])))

    def test_inconsistent_atom_bit_matrix_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)/'atoms.tsv'
            p.write_text('c\t0\t10\t2\tA,B\t1\t0\n')
            with self.assertRaisesRegex(ValueError,'bit matrix'):
                P.read_atoms(p,['A','B'])

    def test_overlap_and_unknown_atom_units_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)/'atoms.tsv'
            for text in ('c\t0\t10\t1\tX\t1\t0\n', 'c\t0\t10\t1\tA\t1\t0\nc\t9\t11\t1\tB\t0\t1\n'):
                p.write_text(text)
                with self.assertRaises(ValueError):
                    P.read_atoms(p,['A','B'])

    def make_context(self,root):
        records,dirs,manifests,qcs = [],[],[],[]
        for i in (1,2):
            d = root/f'p{i}.dir'; d.mkdir()
            peak = d/'peaks.broadPeak'
            peak.write_text(f'c\t{i}\t{i+10}\tpeak\t100\t.\t2\t3\t4\n')
            row = dict(group_id='g',peak_id=f'p{i}',peak_directory=d.name,record_id=f'r{i}',sample_id=f's{i}',
                       dataset='fixture',experiment_id='experiment',condition='condition',target='H3K27me3',
                       genome_id='test',peak_type='broad',caller='macs3',caller_version='3.0.4',
                       biological_replicate=str(i),technical_replicate='1')
            m = root/f'm{i}.json'; q = root/f'q{i}.json'
            m.write_text(json.dumps(dict(row,type='peak_calling',id=f'p{i}',artifacts={'peaks':{'sha256':P.sha(peak)}})))
            q.write_text(json.dumps(dict(row,type='peak_qc_frip',id=f'p{i}')))
            records.append(row); dirs.append(str(d)); manifests.append(str(m)); qcs.append(str(q))
        return records,dirs,manifests,qcs

    def test_context_sets_version_and_requires_matching_source_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            r,d,m,q = self.make_context(Path(directory))
            spec = dict(strategy='regional_catalog',min_replicates=2,replicate_mode='biological',replicate_policy='require_premerged')
            result = C.build_request(r,d,m,q,spec)
            self.assertEqual((result['provider'],result['provider_version']),('regional_catalog_v1','1.0.0'))
            self.assertTrue(all(x['peak_sha256'] for x in result['replicates']))
            (Path(d[0])/'peaks.broadPeak').write_text('c\t1\t13\tchanged\t100\t.\t2\t3\t4\n')
            with self.assertRaisesRegex(ValueError,'checksum'):
                C.build_request(r,d,m,q,spec)

    def test_provider_rejects_duplicate_units_and_fractional_threshold(self):
        with tempfile.TemporaryDirectory() as directory:
            r,d,m,q = self.make_context(Path(directory))
            spec = dict(strategy='regional_catalog',min_replicates=2,replicate_mode='biological',replicate_policy='require_premerged')
            result = C.build_request(r,d,m,q,spec)
            result['replicates'][1]['evidence_replicate_id']='1'
            with self.assertRaisesRegex(ValueError,'Distinct'):
                P.validate_request(result,{Path(p).name:Path(p) for p in d})
            spec['min_replicates']=2.5
            with self.assertRaisesRegex(ValueError,'integer'):
                C.build_request(r,d,m,q,spec)

    def test_narrow_inputs_rejected(self):
        r = [dict(dataset='d',experiment_id='e',condition='c',target='t',genome_id='g',peak_type='narrow',biological_replicate=str(i),technical_replicate='1') for i in (1,2)]
        with self.assertRaisesRegex(ValueError,'broadPeak'):
            C.build_request(r,[],[],[],dict(strategy='regional_catalog'))

    def test_aggregate_accepts_regional_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)/'manifest.json'
            p.write_text(json.dumps(dict(type='consensus',id='g',strategy='regional_catalog',status='complete')))
            self.assertIn('g',A.load_manifests([str(p)]))

    def test_source_is_a_staged_cache_input_and_default_provider_is_untouched(self):
        module = (ROOT/'modules/local/regional_catalog/main.nf').read_text()
        self.assertIn('path(program)',module)
        self.assertIn("cache 'deep'",module)
        self.assertIn('stub:',module)
        old = (ROOT/'modules/local/consensus_intervals/resources/usr/bin/run_consensus.py').read_text()
        self.assertNotIn('regional_catalog',old)


if __name__ == '__main__':
    unittest.main()
