nextflow.enable.dsl = 2

include { PEAK_ANNOTATION } from '../../subworkflows/local/chipseq/peak_annotation'

workflow {
    fixture = file(params.fixture_dir, checkIfExists: true)
    meta = [id: 'fixture.peaks.annotation', source_id: 'fixture.peaks', genome_id: 'fixture_v1', organism: 'fixture']
    spec = [
        provider: 'python_interval_v1', mode: 'overlap_priority', overlap_mode: 'any',
        promoter_upstream: 2000, promoter_downstream: 500, max_tss_distance: null,
        feature_priority: ['promoter', 'exon', 'intron', 'downstream', 'gene'],
        gene_assignment: 'first', strand_aware: false, intergenic_policy: 'retain'
    ]
    spec_base64 = groovy.json.JsonOutput.toJson(spec).getBytes('UTF-8').encodeBase64().toString()
    inputs = channel.value(tuple(
        meta,
        file("${fixture}/fixture.peaks.bed", checkIfExists: true),
        file("${fixture}/peak_manifest.json", checkIfExists: true),
        file("${fixture}/reference.fa", checkIfExists: true),
        file("${fixture}/reference_manifest.json", checkIfExists: true),
        file("${fixture}/annotation.gtf", checkIfExists: true),
        spec_base64
    ))
    PEAK_ANNOTATION(inputs)
}
