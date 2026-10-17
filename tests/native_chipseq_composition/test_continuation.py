import copy
import json
import tempfile
import unittest
from .test_plan import load
from .generate_fixture import generate, indexed_request

CONTEXT = load('continuation_context', 'modules/local/chipseq_continuation_context/validate.py')


class ContinuationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = generate(self.temp.name)
        self.request, self.paths = indexed_request(self.root)

    def change(self, name, update):
        path = self.root / name
        doc = json.loads(path.read_text())
        update(doc)
        path.write_text(json.dumps(doc))

    def test_consensus_and_idr_identity(self):
        for kind in ('consensus', 'idr'):
            request, paths = indexed_request(self.root, kind)
            result = CONTEXT.validate(request, paths)
            self.assertEqual(result['differential_binding'], 'not_requested')
            self.assertEqual(len(result['records']), 3)
            self.assertEqual(result['peaks'][0]['meta']['artifact_type'], 'idr_peaks' if kind == 'idr' else 'consensus_peaks')
            self.assertEqual(result['records'][1]['meta']['biological_replicate'], '1')

    def test_missing_file_is_not_rebuilt(self):
        (self.root / 'ip1.bam').unlink()
        with self.assertRaisesRegex(ValueError, 'missing'):
            CONTEXT.validate(self.request, self.paths)

    def test_changed_bam_checksum_is_rejected(self):
        (self.root / 'ip1.bam').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'BAM checksum'):
            CONTEXT.validate(self.request, self.paths)

    def test_wrong_reference_is_rejected(self):
        self.change('reference.json', lambda doc: doc.update(genome_id='other'))
        with self.assertRaisesRegex(ValueError, 'reference identity'):
            CONTEXT.validate(self.request, self.paths)

    def test_wrong_mark_or_replica_is_rejected(self):
        for key, value in [('target', 'H3K27me3'), ('technical_replicate', '99')]:
            generate(self.root)
            self.change('consensus.json', lambda doc: doc.update(target=value) if key == 'target' else doc['replicates'][0].update({key: value}))
            with self.assertRaisesRegex(ValueError, 'mismatch|conflict'):
                CONTEXT.validate(copy.deepcopy(self.request), self.paths)

    def test_missing_metadata_checksum_is_rejected(self):
        self.change('metadata.json', lambda doc: doc['artifacts']['metadata'].pop('sha256'))
        with self.assertRaisesRegex(ValueError, 'metadata checksum'):
            CONTEXT.validate(self.request, self.paths)

    def test_duplicate_peak_set_is_rejected(self):
        self.request['peaks'] *= 2
        with self.assertRaisesRegex(ValueError, 'unique consensus'):
            CONTEXT.validate(self.request, self.paths)

    def test_unfinished_provider_is_rejected(self):
        self.change('consensus.json', lambda doc: doc.update(status='failed'))
        with self.assertRaisesRegex(ValueError, 'completed producer'):
            CONTEXT.validate(self.request, self.paths)

    def test_bam_metadata_conflict_is_rejected(self):
        self.change('ip1.json', lambda doc: doc.update(sample_id='wrong'))
        with self.assertRaisesRegex(ValueError, 'metadata conflict'):
            CONTEXT.validate(self.request, self.paths)

    def test_source_links_are_retained(self):
        result = CONTEXT.validate(self.request, self.paths)
        self.assertIn('fixture.consensus', result['source_manifest_ids'])
        self.assertEqual(result['records'][1]['meta']['source_manifest_id'], 'ip1')
