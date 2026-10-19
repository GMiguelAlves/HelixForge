"""New aligned-read data for provider validation, not a sequencing benchmark."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import subprocess


def write_library(path, rng, protocol, domains, unit, condition, control):
    contigs = protocol['contigs']
    read_length = protocol['read_length']
    count = 0
    with path.open('w') as out:
        out.write('@HD\tVN:1.6\tSO:unsorted\n')
        for chrom,length in contigs.items():
            out.write(f'@SQ\tSN:{chrom}\tLN:{length}\n')

        def emit(chrom, start, end):
            nonlocal count
            frag = max(protocol['fragment_clip_bp'][0],min(protocol['fragment_clip_bp'][1],round(rng.gauss(protocol['fragment_mean_bp'],protocol['fragment_sd_bp']))))
            if end-start <= frag:
                return
            left = rng.randint(start,end-frag)
            minus = rng.random() < .5
            position = left+frag-read_length if minus else left
            count += 1
            out.write(f'r{count}\t{16 if minus else 0}\t{chrom}\t{position+1}\t60\t{read_length}M\t*\t0\t0\t'+ 'A'*read_length+'\t'+'I'*read_length+'\n')

        for chrom,length in contigs.items():
            for _ in range(round(length*protocol['background_reads_per_bp'])):
                emit(chrom,5,length-5)
        if not control and condition != 'null':
            for domain in domains:
                if unit not in domain['active_units']:
                    continue
                enrichment = (protocol['private_domain_enrichment'] if domain['private_unit'] == unit else 1) if domain['private_unit'] is not None else protocol['enrichment'][condition][unit]
                extra = round((domain['end']-domain['start'])*protocol['background_reads_per_bp']*(enrichment-1))
                for _ in range(extra):
                    if condition == 'variable_signal' and domain['private_unit'] is None:
                        # Position-biased thinning of a fixed excess component;
                        # valleys are part of a declared domain-envelope truth.
                        width = domain['end']-domain['start']
                        center = domain['start']+width*(.35+.15*unit)
                        probe = rng.uniform(domain['start'],domain['end'])
                        if abs(probe-center) < width*.1 and rng.random() > .02:
                            continue
                        left = max(domain['start'],int(probe)-100)
                        right = min(domain['end'],left+400)
                        if right-left < 271:
                            left,right = domain['start'],domain['end']
                        emit(domain['chrom'],left,right)
                    else:
                        emit(domain['chrom'],domain['start'],domain['end'])
    return count


def simulate(protocol, seed, scenario, output):
    if output.exists():
        raise ValueError('Refuse to overwrite synthetic inputs')
    output.mkdir(parents=True)
    contigs = list(protocol['contigs'])
    domains, previous_end = [], {}
    for i in range(protocol['shared_domains']+protocol['private_domains']):
        chrom = contigs[i%len(contigs)]
        j = i//len(contigs)
        width = protocol['width_classes_bp'][min(i//8,2)]
        start = 20000+(j//2)*250000 if j%2 == 0 else previous_end[chrom]+protocol['adjacent_domain_gap_bp']
        previous_end[chrom] = start+width
        domains.append({'id':f'D{i+1:03d}','chrom':chrom,'start':start,'end':start+width,
                        'width_class':width,'private_unit':(i-protocol['shared_domains'])%3 if i >= protocol['shared_domains'] else None})
    active = []
    for d in domains:
        if scenario == 'null':
            units = []
        elif d['private_unit'] is not None:
            units = [d['private_unit']] if scenario == 'library_specific' else []
        else:
            units = [i for i,e in enumerate(protocol['enrichment'][scenario]) if e > 1]
        active.append({**d,'active_units':units})
    (output/'truth.json').write_text(json.dumps(active,indent=2)+'\n')
    for label,subset in (('any_truth',[d for d in active if d['active_units']]),('shared_truth',[d for d in active if len(d['active_units']) >= 2])):
        (output/f'{label}.bed').write_text(''.join(f"{d['chrom']}\t{d['start']}\t{d['end']}\t{d['id']}\n" for d in subset))
    (output/'genome.sizes').write_text(''.join(f'{c}\t{length}\n' for c,length in protocol['contigs'].items()))
    libraries = []
    for unit in range(3):
        for control in (False,True):
            name = f'{"input" if control else "ip"}{unit+1}'
            path = output/(name+'.sam')
            # Seed by role, unit and scenario; no reused IP/Input random stream.
            subseed = int.from_bytes(hashlib.sha256(f'{seed}:{scenario}:{unit}:{control}'.encode()).digest()[:8],'big')
            n = write_library(path,random.Random(subseed),protocol,active,unit,scenario,control)
            bam = output/(name+'.bam')
            subprocess.run(['samtools','sort','-@','1','-o',str(bam),str(path)],check=True)
            subprocess.run(['samtools','index',str(bam)],check=True)
            subprocess.run(['samtools','quickcheck','-v',str(bam)],check=True)
            libraries.append({'id':name,'unit':unit+1,'control':control,'reads':n,'path':bam.name})
    (output/'libraries.json').write_text(json.dumps(libraries,indent=2)+'\n')
    return active


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--protocol',type=Path,required=True)
    p.add_argument('--seed',type=int,required=True)
    p.add_argument('--scenario',required=True)
    p.add_argument('--output',type=Path,required=True)
    a = p.parse_args()
    simulate(json.loads(a.protocol.read_text()),a.seed,a.scenario,a.output)
