"""Validate ChIP stage composition before scheduling scientific producers."""
import argparse
import base64
from collections import defaultdict
import csv
import json
from pathlib import Path

STAGES = ['qc', 'alignment', 'bam', 'peak', 'peak_qc', 'consensus_idr',
          'differential_binding', 'annotation', 'tracks', 'report']
ENDS = dict(qc=0, alignment=1, post_alignment=2, peaks=3, peak_qc=4,
            consensus=5, idr=5, differential_binding=6, full=9)


def build_plan(rows, request, spec=None, db_helpers=None):
    mode = request['mode']
    if mode not in ENDS or not rows:
        raise ValueError('invalid mode or empty ChIP metadata')
    db = request['differential_binding']
    postprocess = request['postprocess']
    if not isinstance(db, bool) or not isinstance(postprocess, bool):
        raise ValueError('stage selections must be boolean')
    if db and mode not in {'full', 'differential_binding'}:
        raise ValueError('Differential Binding requires full or differential_binding mode')
    if mode == 'differential_binding' and not db:
        raise ValueError('differential_binding mode cannot disable its own stage')
    requested = set(STAGES[:ENDS[mode] + 1]) - {'differential_binding'}
    if db:
        requested.add('differential_binding')
    if postprocess:
        requested.update(('annotation', 'tracks', 'report'))
        identities = {(r['dataset'], r['genome_id'], r.get('organism')) for r in rows}
        if len(identities) != 1 or any(not r.get('annotation_file') for r in rows):
            raise ValueError('postprocessing requires one dataset/reference and an annotation for every record')
    if db:
        if spec is None or db_helpers is None:
            raise ValueError('requested Differential Binding requires an explicit specification')
        # Reuse the scientific policy/rank checks from the existing provider.
        db_helpers['validate_spec'](spec)
        groups = defaultdict(list)
        for row in rows:
            if str(row.get('is_control')).lower() not in {'true', '1', 'yes', 'y'}:
                groups[(row['dataset'], row['target'], row['genome_id'])].append(row)
        if not groups:
            raise ValueError('Differential Binding has no IP samples')
        for samples in groups.values():
            if len({r['sample_id'] for r in samples}) != len(samples):
                raise ValueError('technical runs must be premerged before Differential Binding')
            if len({(r['condition'], r['biological_replicate']) for r in samples}) != len(samples):
                raise ValueError('technical records are not independent biological replicates')
            layouts = {r['layout'] for r in samples}
            unit = 'fragments' if layouts == {'paired'} else 'reads'
            if len(layouts) != 1 or spec['counting']['unit'] != unit:
                raise ValueError('Differential Binding layout/counting unit mismatch')
            for contrast in spec['contrasts']:
                for condition in (contrast['numerator'], contrast['denominator']):
                    if sum(r['condition'] == condition for r in samples) < int(spec['parameters']['min_replicates']):
                        raise ValueError(f'contrast condition {condition!r} lacks the required biological replicates')
            db_helpers['validate_design'](samples, spec['design'])
    return dict(schema_version='1.0', type='chipseq_execution_plan', id='chipseq.execution_plan',
                status='complete', mode=mode,
                components={stage: 'requested' if stage in requested else 'not_requested' for stage in STAGES})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--metadata', required=True)
    parser.add_argument('--request', required=True)
    parser.add_argument('--db-spec')
    parser.add_argument('--db-helper', required=True)
    args = parser.parse_args()
    namespace = {'__name__': 'helixforge_db_policy'}
    exec(compile(base64.b64decode(args.db_helper), 'db_preflight.py', 'exec'), namespace)
    with open(args.metadata) as handle:
        rows = list(csv.DictReader(handle, delimiter='\t'))
    spec = json.loads(Path(args.db_spec).read_text()) if args.db_spec else None
    result = build_plan(rows, json.loads(base64.b64decode(args.request)), spec, namespace)
    Path('chipseq.execution_plan.json').write_text(json.dumps(result, indent=2) + '\n')
    print('Validated stage composition')


if __name__ == '__main__':
    main()
