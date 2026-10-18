"""Controlled interval-representation review; never recalls peaks or replaces results.

All representations use the same input peak calls and annotation. Gene counts
are outcomes, never selection criteria. Alternative representations are
counterfactual diagnostics, not validated occupancy catalogs.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import statistics


def merge(intervals, touching=True):
    result=[]
    for chrom,start,end in sorted(intervals):
        if start<0 or end<=start:raise ValueError('Invalid half-open interval')
        joins=result and result[-1][0]==chrom and (start<=result[-1][2] if touching else start<result[-1][2])
        if joins:result[-1]=(chrom,result[-1][1],max(end,result[-1][2]))
        else:result.append((chrom,start,end))
    return result


def atomic_support(replicates):
    events=defaultdict(lambda:defaultdict(list))
    for replicate,intervals in sorted(replicates.items()):
        for chrom,start,end in merge(intervals):
            events[chrom][start].append((replicate,1))
            events[chrom][end].append((replicate,-1))
    atoms=[]
    for chrom,positions in sorted(events.items()):
        active=set()
        coordinates=sorted(positions)
        for start,end in zip(coordinates,coordinates[1:]):
            for replicate,change in positions[start]:
                if change==1:active.add(replicate)
                else:active.remove(replicate)
            if active:atoms.append((chrom,start,end,tuple(sorted(active))))
    return atoms


def overlap_bp(region,intervals):
    chrom,start,end=region
    return sum(max(0,min(end,b)-max(start,a)) for c,a,b in intervals if c==chrom and a<end and b>start)


def representations(replicates,minimum_support=2):
    if not 2<=minimum_support<=len(replicates):raise ValueError('Invalid minimum evidence-unit support')
    atoms=atomic_support(replicates)
    core=[(c,a,b) for c,a,b,ids in atoms if len(ids)>=minimum_support]
    flattened=[r for intervals in replicates.values() for r in intervals]
    components=merge(flattened,touching=False)
    regions=[region for region in components if overlap_bp(region,core)>0]
    reciprocal=set()
    # A fixed 50% reciprocal-overlap comparator; not selected/tuned using genes.
    for left,right in itertools.combinations(sorted(replicates),2):
        for x in merge(replicates[left]):
            for y in merge(replicates[right]):
                if x[0]!=y[0]:continue
                overlap=max(0,min(x[2],y[2])-max(x[1],y[1]))
                if overlap and 2*overlap>=x[2]-x[1] and 2*overlap>=y[2]-y[1]:
                    reciprocal.update((x,y))
    if minimum_support!=2:
        # This pairwise comparator has exactly two-unit semantics, not general k-of-n.
        raise ValueError('Review comparator currently requires minimum_support=2')
    return {
        'atomic_core':core,
        'merged_core':merge(core),
        'overlap_supported_regions':regions,
        'reciprocal_50_whole_peaks':merge(reciprocal),
        'full_union_no_replicate_filter':merge(flattened),
    },atoms


def rows(path):
    with path.open(newline='',encoding='utf-8-sig') as f:return list(csv.DictReader(f,delimiter='\t'))


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def load_annotator():
    source=Path(__file__).resolve().parents[2]/'modules/local/peak_annotator/resources/usr/bin/run_peak_annotator.py'
    spec=importlib.util.spec_from_file_location('review_native_annotator',source)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module,source


def annotate(intervals,annotator,indexes,priority):
    first_genes,all_genes=set(),set()
    assignments=[]
    for chrom,start,end in intervals:
        category='intergenic'
        selected=[]
        for feature in priority:
            hits=annotator.overlapping_indexed(indexes[feature],chrom,start,end)
            if hits:
                category=feature
                selected=sorted({hit[3] for hit in hits})[:1]
                break
        first_genes.update(selected)
        for feature in ('gene','promoter','downstream'):
            all_genes.update(hit[3] for hit in annotator.overlapping_indexed(indexes[feature],chrom,start,end))
        assignments.append((chrom,start,end,category,';'.join(selected)))
    return first_genes,all_genes,assignments


def run(evidence,annotation,annotation_manifest,native_annotations,output):
    if output.exists():raise ValueError('Refuse to overwrite an existing review')
    params=json.loads(annotation_manifest.read_text())
    expected=params['inputs']['annotation']['sha256']
    if sha(annotation)!=expected:raise ValueError('Annotation checksum differs from the native analysis')
    parameters=params['parameters']
    if parameters['gene_assignment']!='first' or parameters['mode']!='overlap_priority':
        raise ValueError('This review requires the native overlap-priority/first baseline')
    replicates=defaultdict(list)
    for row in rows(evidence):
        replicates[row['replicate_id']].append((row['chrom'],int(row['start']),int(row['end'])))
    sets,atoms=representations(replicates)
    annotator,annotator_source=load_annotator()
    features=annotator.read_annotation(annotation,parameters['promoter_upstream'],parameters['promoter_downstream'])
    indexes={name:annotator.build_interval_index(group) for name,group in features.items()}
    outcomes={name:annotate(intervals,annotator,indexes,parameters['feature_priority']) for name,intervals in sets.items()}
    gene_support=defaultdict(set)
    for unit,intervals in replicates.items():
        unit_first,_,_=annotate(intervals,annotator,indexes,parameters['feature_priority'])
        for gene in unit_first:gene_support[gene].add(unit)
    native=rows(native_annotations)
    observed=sorted((r['chrom'],int(r['start']),int(r['end']),r['category'],r['gene_ids']) for r in native)
    if observed!=sorted(outcomes['atomic_core'][2]):raise ValueError('Native annotation/geometry baseline was not reproduced exactly')
    union_bp=sum(b-a for _,a,b in sets['full_union_no_replicate_filter'])
    core_bp=sum(b-a for _,a,b in sets['atomic_core'])
    output.mkdir(parents=True)
    summary=[]
    for name,intervals in sets.items():
        widths=[b-a for _,a,b in intervals]
        covered=sum(widths)
        first,all_genes,assignments=outcomes[name]
        summary.append({'representation':name,'regions':len(intervals),'covered_bp':covered,
                        'fraction_of_input_union_bp':covered/union_bp if union_bp else 0,
                        'bases_with_original_support_ge2':sum(overlap_bp(r,sets['atomic_core']) for r in intervals),
                        'min_width_bp':min(widths,default=0),'median_width_bp':statistics.median(widths) if widths else 0,
                        'width_lt200':sum(w<200 for w in widths),'native_priority_first_genes':len(first),
                        'all_body_or_flank_overlap_genes':len(all_genes),
                        'added_first_genes_vs_atomic':len(first-outcomes['atomic_core'][0]),
                        'lost_first_genes_vs_atomic':len(outcomes['atomic_core'][0]-first)})
        with (output/f'{name}.bed').open('w') as f:
            for index,(chrom,start,end) in enumerate(intervals,1):f.write(f'{chrom}\t{start}\t{end}\t{name}.{index:06d}\n')
        with (output/f'{name}.gene_assignments.tsv').open('w') as f:
            f.write('chrom\tstart\tend\tcategory\tgene_ids\n')
            for row in assignments:f.write('\t'.join(map(str,row))+'\n')
    with (output/'summary.tsv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(summary[0]),delimiter='\t',lineterminator='\n');w.writeheader();w.writerows(summary)
    region_support=[]
    for chrom,start,end in sets['overlap_supported_regions']:
        core=overlap_bp((chrom,start,end),sets['atomic_core'])
        present=sorted(rep for rep,intervals in replicates.items() if overlap_bp((chrom,start,end),merge(intervals))>0)
        region_support.append({'chrom':chrom,'start':start,'end':end,'any_overlap_units':','.join(present),
                               'any_overlap_unit_count':len(present),'core_supported_bp':core,
                               'core_fraction':core/(end-start),'unsupported_or_single_unit_bp':end-start-core})
    with (output/'region_support.tsv').open('w',newline='') as f:
        fields=['chrom','start','end','any_overlap_units','any_overlap_unit_count','core_supported_bp','core_fraction','unsupported_or_single_unit_bp']
        w=csv.DictWriter(f,fieldnames=fields,delimiter='\t',lineterminator='\n');w.writeheader();w.writerows(region_support)
    with (output/'gene_level_recurrence.tsv').open('w',newline='') as f:
        fields=['gene_id','evidence_unit_count','evidence_units','in_atomic_first_gene_set','recurs_ge2_without_atomic_association']
        w=csv.DictWriter(f,fieldnames=fields,delimiter='\t',lineterminator='\n');w.writeheader()
        for gene,units in sorted(gene_support.items()):
            w.writerow({'gene_id':gene,'evidence_unit_count':len(units),'evidence_units':','.join(sorted(units)),
                        'in_atomic_first_gene_set':gene in outcomes['atomic_core'][0],
                        'recurs_ge2_without_atomic_association':len(units)>=2 and gene not in outcomes['atomic_core'][0]})
    result={'type':'controlled_broad_interval_representation_review','native_baseline_reconstruction':'PASS',
            'scope':'Fixed peak calls and frozen annotation; no BAM processing, peak recalling, parameter fitting or result replacement.',
            'comparison_is_not_biological_validation':True,'support_units_are_deposited_library_labels':True,
            'parameters':parameters,'union_bp':union_bp,'core_bp':core_bp,'summary':summary,
            'gene_ids':{name:{'first':sorted(value[0]),'all_body_or_flank':sorted(value[1])} for name,value in outcomes.items()},
            'gene_recurrence':{'definition':'Same gene associated with peaks in multiple libraries, not spatial co-occupancy, biological independence, or differential binding.',
                               'genes_in_at_least_one_unit':len(gene_support),
                               'genes_in_at_least_two_units':sum(len(s)>=2 for s in gene_support.values()),
                               'genes_in_all_units':sum(len(s)==len(replicates) for s in gene_support.values()),
                               'recurrent_genes_missing_from_atomic_first':sum(len(s)>=2 and g not in outcomes['atomic_core'][0] for g,s in gene_support.items())},
            'inputs':{label:{'name':path.name,'sha256':sha(path)} for label,path in (
                ('evidence',evidence),('annotation',annotation),('annotation_manifest',annotation_manifest),
                ('native_annotations',native_annotations),('annotation_provider',annotator_source),('review_program',Path(__file__).resolve()))},
            'definitions':{
                'atomic_core':'Half-open atomic subintervals with >=2 distinct evidence units at every base.',
                'merged_core':'Bookended atomic cores merged; identical covered bases, potentially different first-gene assignment.',
                'overlap_supported_regions':'Strictly overlapping connected components of input peaks containing a >=2-unit core. Full envelopes retained; tails need not have replicated support.',
                'reciprocal_50_whole_peaks':'Full peaks with >=50% reciprocal overlap with a peak from a different evidence unit, merged. Diagnostic comparator, not an adopted cutoff.',
                'full_union_no_replicate_filter':'All called bases without a reproducibility filter; a diagnostic upper bound, not a validated consensus.'}}
    (output/'review.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('evidence','annotation','annotation-manifest','native-annotations','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    result=run(args.evidence,args.annotation,args.annotation_manifest,args.native_annotations,args.output)
    print(json.dumps({'baseline':result['native_baseline_reconstruction'],'summary':result['summary']},indent=2))


if __name__=='__main__':main()
