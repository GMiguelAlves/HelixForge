"""Execute a frozen synthetic case inside a compute allocation."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from simulate import simulate
from evaluate import evaluate


def load(name,path):
    spec = importlib.util.spec_from_file_location(name,path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--case',type=int,required=True)
    args = parser.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):
        raise RuntimeError('All scientific execution requires Slurm')
    protocol_path = Path(__file__).with_name('protocol.json')
    protocol = json.loads(protocol_path.read_text())
    cases = [(s,c) for s in protocol['seeds'] for c in protocol['scenarios']]
    if not 0 <= args.case < len(cases) or protocol['replicates'] != 3:
        raise ValueError('Unsupported case index or replicate design')
    seed,scenario = cases[args.case]
    case = args.output/f'{seed}-{scenario}'
    case.mkdir(parents=True,exist_ok=False)
    start = time.time()
    simulate(protocol,seed,scenario,case/'inputs')
    provider = load('provider',args.repo/'modules/local/regional_catalog/resources/usr/bin/run_regional_catalog.py')
    context = load('context',args.repo/'modules/local/consensus_context/resources/usr/bin/validate_consensus_context.py')
    if subprocess.check_output(['macs3','--version'],text=True).strip() != 'macs3 '+protocol['macs3']['version']:
        raise ValueError('Unexpected MACS3 version')
    records,dirs,manifests,qcs,peaks = [],[],[],[],[]
    for i in (1,2,3):
        d = case/f'ip{i}.peak_calling'
        d.mkdir()
        params = protocol['macs3']
        if not params['nomodel']:
            raise ValueError('Validation protocol requires its known simulated fragment model')
        command = ['macs3','callpeak','-t',str(case/f'inputs/ip{i}.bam'),'-c',str(case/f'inputs/input{i}.bam'),
                   '-f',params['format'],'-g',str(sum(protocol['contigs'].values())),'-n',f'ip{i}','--outdir',str(d),
                   '--keep-dup',params['keep_dup'],'-q',str(params['q_value']),'--broad','--broad-cutoff',str(params['broad_cutoff']),
                   '--nomodel','--extsize',str(params['extsize']),'--shift',str(params['shift'])]
        (d/'command.json').write_text(json.dumps(command,indent=2)+'\n')
        with (d/'macs.log').open('w') as log:
            subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True)
        p = d/'peaks.broadPeak'
        shutil.copy2(d/f'ip{i}_peaks.broadPeak',p)
        n = sum(bool(line.strip()) for line in p.read_text().splitlines())
        row = {'group_id':f'validation.{seed}.{scenario}','peak_id':f'ip{i}','peak_directory':d.name,
               'record_id':f'ip{i}','sample_id':f'ip{i}','dataset':'independent_synthetic',
               'experiment_id':f'validation.{seed}.{scenario}','condition':scenario,'target':'synthetic_broad',
               'genome_id':'regional_validation_v1','peak_type':'broad','caller':'macs3','caller_version':'3.0.4',
               'biological_replicate':str(i),'technical_replicate':'1'}
        manifest = d/'manifest.json'
        manifest.write_text(json.dumps({**row,'id':f'ip{i}','type':'peak_calling','status':'complete' if n else 'complete_empty',
                                       'artifacts':{'peaks':{'path':p.name,'sha256':provider.sha(p)}}},indent=2)+'\n')
        # Real FRiP diagnostic, not an invented QC-success marker.
        proc = subprocess.Popen(['bedtools','intersect','-u','-abam',str(case/f'inputs/ip{i}.bam'),'-b',str(p)],stdout=subprocess.PIPE)
        counted = subprocess.run(['samtools','view','-c'],stdin=proc.stdout,capture_output=True,text=True,check=True)
        proc.stdout.close()
        if proc.wait() != 0:
            raise RuntimeError('FRiP intersection failed')
        inside = int(counted.stdout)
        total = int(subprocess.check_output(['samtools','view','-c',str(case/f'inputs/ip{i}.bam')],text=True))
        qc = d/'qc.json'
        qc.write_text(json.dumps({**row,'id':f'ip{i}','type':'peak_qc_frip','metrics':{'reads_in_peaks':inside,'mapped_reads':total,'frip':inside/total}},indent=2)+'\n')
        records.append(row); dirs.append(str(d)); manifests.append(str(manifest)); qcs.append(str(qc)); peaks.append(p)
    spec = {'strategy':'regional_catalog','min_replicates':2,'replicate_mode':'biological','replicate_policy':'require_premerged','require_same_caller':True}
    request = context.build_request(records,dirs,manifests,qcs,spec)
    (case/'request.json').write_text(json.dumps(request,indent=2)+'\n')
    result,execution = provider.run(request,dirs,case/'catalog',case/'provider_reports',2,4*1024**3,'2h','standalone-provider-validation','certified_conda')
    # Independent reference core: run BEDTools from each original caller set,
    # without importing production geometry or its atomic parser.
    merged = []
    for i,p in enumerate(peaks):
        sorted_peaks = subprocess.run(['bedtools','sort','-i',str(p)],capture_output=True,text=True,check=True)
        union = subprocess.run(['bedtools','merge','-i','stdin'],input=sorted_peaks.stdout,capture_output=True,text=True,check=True)
        dest = case/f'independent_unit{i}.bed'
        dest.write_text(union.stdout); merged.append(str(dest))
    atomic = subprocess.check_output(['bedtools','multiinter','-i',*merged],text=True) if any(p.stat().st_size for p in peaks) else ''
    (case/'independent_core.bed').write_text(''.join('\t'.join(f[:3])+'\n' for line in atomic.splitlines() if (f:=line.split('\t')) and int(f[3]) >= 2))
    report = evaluate(case,protocol,scenario,peaks)
    report.update({'seed':seed,'seconds':time.time()-start,'job':os.environ['SLURM_JOB_ID'],
                   'protocol_sha256':provider.sha(protocol_path),'provider_source_sha256':provider.sha(args.repo/'modules/local/regional_catalog/resources/usr/bin/run_regional_catalog.py')})
    (case/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'seed':seed,'scenario':scenario,'status':report['status'],'checks':report['checks']}))
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
