import gzip
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('read_audit', ROOT / 'modules/local/read_trimming_audit/audit_reads.py')
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class TrimmingContractTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.r1 = self.write('r1.fastq', '@read/1\nACGT\n+\nIIII\n')
        self.r2 = self.write('r2.fq.gz', '@read/2\nTGCA\n+\nIIII\n', True)
        self.meta = dict(id='ip.run1', sample_id='ip', single_end=False, is_control=False,
                         control_id='input.run1', biological_replicate='1', technical_replicate='2',
                         condition='adult', target='H3K4me3', dataset='fixture', genome_id='fixture_v1')
        self.policy = AUDIT.policy(20, 20)

    def write(self, name, text, zipped=False):
        path = self.root / name
        path.write_bytes(gzip.compress(text.encode()) if zipped else text.encode())
        return path

    def test_paired_plain_and_gzip(self):
        result = AUDIT.audit(self.meta, [self.r1, self.r2], self.policy)
        self.assertEqual([r['records'] for r in result['reads']], [1, 1])
        self.assertEqual(result['control_id'], 'input.run1')
        self.assertEqual(result['technical_replicate'], '2')

    def test_single(self):
        result = AUDIT.audit(dict(self.meta, single_end=True), [self.r1], self.policy)
        self.assertEqual(len(result['reads']), 1)

    def test_mismatched_ids(self):
        self.r2 = self.write('wrong.fastq', '@other/2\nTGCA\n+\nIIII\n')
        with self.assertRaisesRegex(ValueError, 'mismatched'):
            AUDIT.inspect_reads([self.r1, self.r2], False)

    def test_unbalanced_pairs(self):
        self.r2 = self.write('short.fastq', '')
        with self.assertRaisesRegex(ValueError, 'different record counts'):
            AUDIT.inspect_reads([self.r1, self.r2], False)

    def test_bad_record(self):
        for content in ('@read\nACGT\n+\nIII\n', '@read\nACGT\n', '@read\nZZZZ\n+\nIIII\n'):
            with self.subTest(content=content), self.assertRaises(ValueError):
                AUDIT.inspect_reads([self.write('bad.fq', content)], True)

    def test_reversed_mates_and_reused_file(self):
        with self.assertRaisesRegex(ValueError, 'mate labels'):
            AUDIT.inspect_reads([self.r2, self.r1], False)
        with self.assertRaisesRegex(ValueError, 'distinct'):
            AUDIT.inspect_reads([self.r1, self.r1], False)

    def test_empty_and_wrong_cardinality(self):
        with self.assertRaisesRegex(ValueError, 'no reads'):
            AUDIT.inspect_reads([self.write('empty.fq', '')], True)
        with self.assertRaisesRegex(ValueError, 'cardinality'):
            AUDIT.inspect_reads([self.r1], False)

    def test_truncated_gzip(self):
        path = self.root / 'truncated.gz'
        path.write_bytes(gzip.compress(b'@read\nACGT\n+\nIIII\n')[:-8])
        with self.assertRaises((EOFError, OSError)):
            AUDIT.inspect_reads([path], True)

    def test_policy_requires_explicit_values_and_safe_adapters(self):
        for quality, length, adapter in ((None, 20, None), (20, None, None), (-1, 20, None),
                                         (41, 20, None), (20, 0, None), (20, 20, "A'; false")):
            with self.subTest(quality=quality, length=length), self.assertRaises(ValueError):
                AUDIT.policy(quality, length, adapter)

    def test_adapter2_requires_read1_and_paired(self):
        with self.assertRaises(ValueError):
            AUDIT.policy(20, 20, None, 'ACGT')
        with self.assertRaisesRegex(ValueError, 'single-end'):
            AUDIT.audit(dict(self.meta, single_end=True), [self.r1], AUDIT.policy(20, 20, 'ACGT', 'ACGT'))

    def test_post_audit_preserves_identity_and_checksums(self):
        prior = AUDIT.audit(self.meta, [self.r1, self.r2], self.policy)
        observed = AUDIT.audit(self.meta, [self.r1, self.r2], self.policy, prior,
                               {'trim_galore': '0.6.10', 'cutadapt': '4.9'})
        self.assertEqual(observed['type'], 'read_trimming')
        self.assertEqual(observed['retained_fraction'], 1)
        self.assertEqual(observed['raw_reads'], prior['reads'])
        self.assertEqual(observed['reads'][0]['sha256'], AUDIT.sha256(self.r1))
        for key in ('sample_id', 'control_id', 'is_control', 'biological_replicate', 'technical_replicate', 'target'):
            self.assertEqual(observed[key], self.meta[key])

    def test_changed_metadata_or_missing_versions_rejected(self):
        prior = AUDIT.audit(self.meta, [self.r1, self.r2], self.policy)
        with self.assertRaisesRegex(ValueError, 'metadata changed'):
            AUDIT.audit(dict(self.meta, control_id='other'), [self.r1, self.r2], self.policy, prior)
        with self.assertRaisesRegex(ValueError, 'versions'):
            AUDIT.audit(self.meta, [self.r1, self.r2], self.policy, prior)
