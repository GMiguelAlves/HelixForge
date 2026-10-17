import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PLAN = load('chip_plan', 'modules/local/chipseq_execution_plan/plan.py')
DB = load('existing_db', 'modules/local/db_preflight/resources/usr/bin/db_preflight.py')


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.rows = [dict(record_id=f'{condition}.{i}', sample_id=f'{condition}.{i}', dataset='fixture',
                          genome_id='v1', organism='fixture', annotation_file='reference.gtf',
                          target='H3K4me3', condition=condition, biological_replicate=str(i),
                          technical_replicate='1', layout='paired', is_control='false')
                     for condition in ('control', 'treated') for i in (1, 2)]
        self.spec = json.loads((ROOT / 'assets/chipseq_db_spec.example.json').read_text())
        self.request = dict(mode='full', differential_binding=False, postprocess=True)

    def test_full_without_db(self):
        plan = PLAN.build_plan(self.rows, self.request)
        self.assertEqual(plan['components']['differential_binding'], 'not_requested')
        self.assertEqual(plan['components']['report'], 'requested')

    def test_existing_db_policy_is_reused(self):
        plan = PLAN.build_plan(self.rows, dict(self.request, differential_binding=True), self.spec, vars(DB))
        self.assertEqual(plan['components']['differential_binding'], 'requested')

    def test_consensus_and_idr_can_continue_without_db(self):
        for mode in ('consensus', 'idr'):
            plan = PLAN.build_plan(self.rows, dict(self.request, mode=mode))
            self.assertEqual(plan['components']['tracks'], 'requested')
            self.assertEqual(plan['components']['differential_binding'], 'not_requested')

    def test_missing_contrast_is_rejected(self):
        self.spec['contrasts'] = []
        with self.assertRaisesRegex(ValueError, 'contrast'):
            PLAN.build_plan(self.rows, dict(self.request, differential_binding=True), self.spec, vars(DB))

    def test_unknown_condition_or_insufficient_replication_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'replicates'):
            PLAN.build_plan(self.rows[:3], dict(self.request, differential_binding=True), self.spec, vars(DB))

    def test_technical_runs_are_not_replicates(self):
        rows = copy.deepcopy(self.rows)
        rows[1]['sample_id'] = rows[0]['sample_id']
        with self.assertRaisesRegex(ValueError, 'premerged'):
            PLAN.build_plan(rows, dict(self.request, differential_binding=True), self.spec, vars(DB))

    def test_confounded_batch_is_rejected(self):
        for row in self.rows:
            row['batch'] = row['condition']
        self.spec['design'] = dict(formula='~ batch + condition', variable='condition', covariates=['batch'])
        with self.assertRaisesRegex(ValueError, 'rank deficient'):
            PLAN.build_plan(self.rows, dict(self.request, differential_binding=True), self.spec, vars(DB))

    def test_missing_annotation_or_mixed_reference_is_rejected(self):
        for field, value in [('annotation_file', ''), ('genome_id', 'other')]:
            rows = copy.deepcopy(self.rows)
            rows[0][field] = value
            with self.assertRaisesRegex(ValueError, 'annotation'):
                PLAN.build_plan(rows, self.request)

    def test_simple_modes_do_not_request_postprocessing(self):
        plan = PLAN.build_plan(self.rows, dict(mode='alignment', differential_binding=False, postprocess=False))
        self.assertEqual(plan['components']['alignment'], 'requested')
        self.assertEqual(plan['components']['annotation'], 'not_requested')
