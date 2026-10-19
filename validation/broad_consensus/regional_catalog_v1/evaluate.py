"""Independent BEDTools-based evaluation; does not import provider algorithms."""
import json
from pathlib import Path
import subprocess


def bed(path):
    return [(f[0],int(f[1]),int(f[2])) for line in Path(path).read_text().splitlines() if line.strip() and (f:=line.split('\t'))]


def merged(source,target):
    sort = subprocess.run(['bedtools','sort','-i',str(source)],check=True,capture_output=True,text=True)
    result = subprocess.run(['bedtools','merge','-i','stdin'],input=sort.stdout,check=True,capture_output=True,text=True)
    target.write_text(result.stdout)
    return bed(target)


def metric(calls,truth,work,label):
    rows = bed(calls)
    merged_path = work/f'{label}.merged.bed'
    merged_rows = merged(calls,merged_path)
    truth_rows = bed(truth)
    truth_bp = sum(b-a for c,a,b in truth_rows)
    called_bp = sum(b-a for c,a,b in merged_rows)
    overlaps = subprocess.run(['bedtools','intersect','-a',str(merged_path),'-b',str(truth),'-wo'],capture_output=True,text=True,check=True).stdout if truth_rows and merged_rows else ''
    covered_bp = sum(int(line.split('\t')[-1]) for line in overlaps.splitlines())
    domains = []
    merging_ids = set()
    degrees = [0]*len(truth_rows)
    for c,a,b in rows:
        hits = []
        for i,(chrom,start,end) in enumerate(truth_rows):
            overlap = max(0,min(b,end)-max(a,start)) if c == chrom else 0
            if overlap >= 500 or overlap >= .1*(end-start):
                hits.append(i)
                degrees[i] += 1
        if len(hits) > 1:
            merging_ids.update(hits)
    recovered = 0
    for i,(c,a,b) in enumerate(truth_rows):
        overlap = sum(max(0,min(b,end)-max(a,start)) for chrom,start,end in merged_rows if chrom == c)
        found = overlap/(b-a) >= .5
        recovered += found
        domains.append({'chrom':c,'start':a,'end':b,'coverage_recall':overlap/(b-a),
                        'recovered':found,'substantial_call_degree':degrees[i],'fragmented':degrees[i] > 1})
    width_strata = {}
    for width in sorted({d['end']-d['start'] for d in domains}):
        subset = [d for d in domains if d['end']-d['start'] == width]
        width_strata[str(width)] = {'domains':len(subset),'domain_recall':sum(d['recovered'] for d in subset)/len(subset),
                                   'fragmentation_fraction':sum(d['fragmented'] for d in subset)/len(subset)}
    return {'records':len(rows),'called_bp':called_bp,'truth_bp':truth_bp,
            'true_positive_bp':covered_bp,'false_positive_bp':called_bp-covered_bp,
            'base_precision':covered_bp/called_bp if called_bp else None,
            'base_recall':covered_bp/truth_bp if truth_bp else None,
            'domain_recall':recovered/len(truth_rows) if truth_rows else None,
            'fragmentation_fraction':sum(d['fragmented'] for d in domains)/len(domains) if domains else None,
            'merging_fraction':len(merging_ids)/len(truth_rows) if truth_rows else None,
            'domains':domains,'width_strata':width_strata}


def evaluate(case,protocol,scenario,replicate_peaks):
    target = case/'evaluation'
    target.mkdir(exist_ok=False)
    result = case/'catalog'
    files = {'candidate':result/'consolidated_peaks.bed','supported':result/'supported_regions.bed',
             'core':case/'independent_core.bed'}
    any_truth,shared_truth = case/'inputs/any_truth.bed',case/'inputs/shared_truth.bed'
    metrics = {name:metric(path,any_truth if name == 'candidate' else shared_truth,target,name) for name,path in files.items()}
    (target/'all_source_peaks.bed').write_text(''.join(Path(p).read_text() for p in replicate_peaks))
    expected_union = merged(target/'all_source_peaks.bed',target/'expected_union.bed')
    catalog = bed(files['candidate'])
    same_union = catalog == expected_union
    expected_core = bed(files['core'])
    observed_core = bed(result/'core_supported.bed')
    split = sum(sum(c == chrom and a <= start and b >= end for c,a,b in catalog) != 1
                for peak in replicate_peaks for chrom,start,end in bed(peak))
    gates = protocol['gates']
    checks = {'catalog_union_exact':same_union, 'core_matches_independent_bedtools':observed_core == expected_core,
              'original_calls_not_split':split == gates['original_calls_split']}
    if scenario == 'null':
        checks['null_supported_regions'] = metrics['supported']['records'] <= gates['null_supported_regions_max']
        checks['null_candidate_genome_fraction'] = metrics['candidate']['called_bp']/sum(protocol['contigs'].values()) <= gates['null_candidate_genome_fraction_max']
    else:
        checks['candidate_base_precision'] = metrics['candidate']['base_precision'] is not None and metrics['candidate']['base_precision'] >= gates['candidate_base_precision_min']
        checks['supported_shared_base_precision'] = metrics['supported']['base_precision'] is not None and metrics['supported']['base_precision'] >= gates['supported_shared_base_precision_min']
        recall = metrics['supported']['domain_recall']
        checks['shared_domain_recall'] = recall is not None and recall >= gates['shared_domain_recall_min'][scenario]
        for width,stratum in metrics['supported']['width_strata'].items():
            checks['shared_domain_recall_width_'+width] = stratum['domain_recall'] >= gates['shared_domain_recall_min'][scenario]
        checks['recall_loss_vs_core'] = recall is not None and recall+gates['supported_domain_recall_loss_vs_core_max'] >= metrics['core']['domain_recall']
        checks['fragmentation_increase_vs_core'] = metrics['supported']['fragmentation_fraction'] <= metrics['core']['fragmentation_fraction']+gates['supported_domain_fragmentation_increase_vs_core_max']
        checks['truth_merging_fraction'] = metrics['supported']['merging_fraction'] <= gates['supported_truth_merging_fraction_max']
        if scenario == 'library_specific':
            truth = json.loads((case/'inputs/truth.json').read_text())
            private = [d for d in truth if len(d['active_units']) == 1]
            intervals = bed(files['supported'])
            recovered = sum(sum(max(0,min(d['end'],b)-max(d['start'],a)) for c,a,b in intervals if c == d['chrom']) >= .5*(d['end']-d['start']) for d in private)
            checks['private_domain_recovery'] = recovered/len(private) <= gates['supported_private_domain_recovery_fraction_max']
    report = {'status':'PASS' if all(checks.values()) else 'FAIL','scenario':scenario,
              'checks':checks,'metrics':metrics,'original_calls_split':split,
              'source':'new aligned-read synthetic inputs; no original benchmark changed',
              'biological_reproducibility_certified':False}
    (target/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    return report
