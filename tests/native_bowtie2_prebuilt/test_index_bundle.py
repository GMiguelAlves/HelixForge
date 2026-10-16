import copy
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('bowtie2_bundle', ROOT / 'modules/local/bowtie2_index/index_bundle.py')
BUNDLE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUNDLE)


class IndexBundleTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.reference = self.root / 'reference.fa'
        self.reference.write_text('>chr1\nACGT\n')
        self.index = self.root / 'index'
        self.index.mkdir()
        self.meta = {'id': 'fixture.index', 'genome_id': 'fixture_v1'}
        self.parameters = {'basename': 'genome', 'extra_args': '--offrate 4'}
        self.write_shards('bt2')
        self.document = BUNDLE.bundle_document(self.index, self.reference, self.meta, self.parameters, '2.5.4')

    def write_shards(self, extension):
        for suffix in BUNDLE.SUFFIXES:
            (self.index / f'genome.{suffix}.{extension}').write_bytes(f'unit-test-shard-{suffix}'.encode())

    def validate(self, document=None, parameters=None, version='2.5.4'):
        return BUNDLE.validate_bundle(self.index, self.reference, document or self.document,
                                      self.meta, parameters or self.parameters, version)

    def test_valid_bundle_and_input_immutability(self):
        original = copy.deepcopy(self.document)
        result = self.validate()
        self.assertEqual(result['index_source'], 'prebuilt')
        self.assertEqual(self.document, original)

    def test_large_bundle(self):
        for path in self.index.iterdir():
            path.unlink()
        self.write_shards('bt2l')
        self.document = BUNDLE.bundle_document(self.index, self.reference, self.meta, self.parameters, '2.5.4')
        self.assertEqual(self.validate()['index_source'], 'prebuilt')

    def test_missing_shard_fails(self):
        (self.index / 'genome.rev.2.bt2').unlink()
        with self.assertRaisesRegex(ValueError, 'six'):
            self.validate()

    def test_empty_shard_fails(self):
        (self.index / 'genome.2.bt2').write_bytes(b'')
        with self.assertRaisesRegex(ValueError, 'six'):
            self.validate()

    def test_mixed_formats_fail(self):
        self.write_shards('bt2l')
        with self.assertRaisesRegex(ValueError, 'six'):
            self.validate()

    def test_changed_shard_fails(self):
        (self.index / 'genome.1.bt2').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'checksums'):
            self.validate()

    def test_reference_change_fails(self):
        self.reference.write_text('>chr1\nTGCA\n')
        with self.assertRaisesRegex(ValueError, 'reference checksum'):
            self.validate()

    def test_version_change_fails(self):
        with self.assertRaisesRegex(ValueError, 'version mismatch'):
            self.validate(version='2.5.3')

    def test_parameters_change_fails(self):
        with self.assertRaisesRegex(ValueError, 'parameters differ'):
            self.validate(parameters={'basename': 'genome', 'extra_args': '--offrate 5'})

    def test_whitespace_in_arguments_is_not_a_change(self):
        result = self.validate(parameters={'basename': 'genome', 'extra_args': '  --offrate   4  '})
        self.assertEqual(result['index_source'], 'prebuilt')

    def test_basename_and_genome_identity_fail(self):
        for field, value in [('basename', 'different'), ('genome_id', 'other')]:
            document = dict(self.document, **{field: value})
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.validate(document)

    def test_old_stub_and_wrong_provider_fail(self):
        for field, value in [('schema_version', '1.1'), ('status', 'stub'), ('aligner', 'star')]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.validate(dict(self.document, **{field: value}))

    def test_tampered_bundle_digest_fails(self):
        with self.assertRaisesRegex(ValueError, 'bundle checksum'):
            self.validate(dict(self.document, bundle_sha256='0' * 64))

    def test_manifest_path_traversal_cannot_select_other_files(self):
        with self.assertRaisesRegex(ValueError, 'basename'):
            BUNDLE.shards(self.index, '../genome')

    def test_bundle_identity_does_not_depend_on_directory_name(self):
        renamed = self.root / 'another_name'
        self.index.rename(renamed)
        self.index = renamed
        self.assertEqual(self.validate()['bundle_sha256'], self.document['bundle_sha256'])


if __name__ == '__main__':
    unittest.main()
