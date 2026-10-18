import importlib.util
import random
import tempfile
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('broad_representation_review',ROOT/'validation/broad_consensus/compare_representations.py')
REVIEW=importlib.util.module_from_spec(spec)
spec.loader.exec_module(REVIEW)


class BroadRepresentationTests(unittest.TestCase):
    def test_one_base_core_does_not_establish_one_base_domain(self):
        results,atoms=REVIEW.representations({'A':[('chr1',0,200)],'B':[('chr1',199,400)]})
        self.assertEqual(results['atomic_core'],[('chr1',199,200)])
        self.assertEqual(results['overlap_supported_regions'],[('chr1',0,400)])
        self.assertEqual(results['reciprocal_50_whole_peaks'],[])
        self.assertEqual(sum(b-a for _,a,b,ids in atoms if len(ids)>=2),1)

    def test_bookending_is_not_replicate_overlap(self):
        results,_=REVIEW.representations({'A':[('chr1',0,200)],'B':[('chr1',200,400)]})
        self.assertEqual(results['atomic_core'],[])
        self.assertEqual(results['overlap_supported_regions'],[])
        self.assertEqual(results['full_union_no_replicate_filter'],[('chr1',0,400)])

    def test_one_unit_cannot_supply_two_units_through_duplicate_peaks(self):
        results,atoms=REVIEW.representations({'A':[('chr1',0,300),('chr1',20,280)],'B':[('chr2',0,300)]})
        self.assertEqual(results['atomic_core'],[])
        self.assertTrue(all(len(ids)==1 for _,_,_,ids in atoms))

    def test_connected_envelope_can_have_unsupported_tails(self):
        results,_=REVIEW.representations({'A':[('chr1',0,1000)],'B':[('chr1',950,1150)]})
        envelope=results['overlap_supported_regions'][0]
        self.assertEqual(envelope,('chr1',0,1150))
        self.assertEqual(REVIEW.overlap_bp(envelope,results['atomic_core']),50)
        self.assertLess(50/(envelope[2]-envelope[1]),0.05)

    def test_merging_cores_preserves_bases_and_does_not_fill_gaps(self):
        results,_=REVIEW.representations({'A':[('chr1',0,500)],'B':[('chr1',100,200),('chr1',300,400)],'C':[('chr1',150,350)]})
        self.assertEqual(results['merged_core'],[('chr1',100,400)])
        self.assertEqual(sum(b-a for _,a,b in results['atomic_core']),300)
        no_bridge,_=REVIEW.representations({'A':[('chr1',0,500)],'B':[('chr1',100,200),('chr1',300,400)]})
        self.assertEqual(no_bridge['merged_core'],[('chr1',100,200),('chr1',300,400)])

    def test_reciprocal_half_overlap_requires_both_peak_fractions(self):
        results,_=REVIEW.representations({'A':[('chr1',0,200)],'B':[('chr1',100,300)]})
        self.assertEqual(results['reciprocal_50_whole_peaks'],[('chr1',0,300)])
        asymmetrical,_=REVIEW.representations({'A':[('chr1',100,300)],'B':[('chr1',0,1000)]})
        self.assertEqual(asymmetrical['reciprocal_50_whole_peaks'],[])

    def test_cross_chromosome_intervals_never_support_each_other(self):
        results,_=REVIEW.representations({'A':[('chr1',0,200)],'B':[('chr2',0,200)]})
        self.assertFalse(results['atomic_core'])
        self.assertFalse(results['overlap_supported_regions'])

    def test_invalid_support_or_coordinates_fail(self):
        with self.assertRaises(ValueError):REVIEW.representations({'A':[('chr1',0,200)]})
        with self.assertRaises(ValueError):REVIEW.merge([('chr1',20,20)])
        with self.assertRaises(ValueError):REVIEW.merge([('chr1',-1,20)])

    def test_atomic_support_matches_independent_per_base_coverage(self):
        rng=random.Random(19)
        for _ in range(30):
            reps={unit:[('chr1',a:=rng.randrange(40),a+rng.randrange(1,15)) for _ in range(5)] for unit in ('A','B','C')}
            results,_=REVIEW.representations(reps)
            covered={unit:{x for _,a,b in intervals for x in range(a,b)} for unit,intervals in reps.items()}
            expected={x for x in range(55) if sum(x in values for values in covered.values())>=2}
            actual={x for _,a,b in results['atomic_core'] for x in range(a,b)}
            merged={x for _,a,b in results['merged_core'] for x in range(a,b)}
            regions={x for _,a,b in results['overlap_supported_regions'] for x in range(a,b)}
            union=set().union(*covered.values())
            self.assertEqual(actual,expected)
            self.assertEqual(merged,expected)
            self.assertTrue(expected<=regions<=union)

    def test_annotation_checksum_mismatch_fails_before_publication(self):
        import json
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            annotation=root/'reference.gtf'
            manifest=root/'manifest.json'
            annotation.write_text('changed annotation\n')
            manifest.write_text(json.dumps({'inputs':{'annotation':{'sha256':'0'*64}}}))
            with self.assertRaisesRegex(ValueError,'checksum'):
                REVIEW.run(root/'evidence.tsv',annotation,manifest,root/'native.tsv',root/'output')
            self.assertFalse((root/'output').exists())

    def test_existing_results_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with self.assertRaisesRegex(ValueError,'overwrite'):
                REVIEW.run(root/'missing',root/'missing',root/'missing',root/'missing',root)


if __name__=='__main__':unittest.main()
