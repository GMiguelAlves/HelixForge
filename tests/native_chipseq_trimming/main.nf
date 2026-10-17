nextflow.enable.dsl = 2
include { READ_TRIMMING } from '../../subworkflows/local/qc/read_trimming'
include { FASTQC as FASTQC_RAW } from '../../modules/local/fastqc/main'
include { FASTQC as FASTQC_POST } from '../../modules/local/fastqc/main'
include { MULTIQC } from '../../modules/local/multiqc/main'
include { REFERENCE_INDEX } from '../../subworkflows/local/alignment/reference_index'
include { ALIGNMENT } from '../../subworkflows/local/alignment/alignment'

workflow {
    def rows = new groovy.json.JsonSlurper().parse(file(params.samples).toFile())
    raw = channel.fromList(rows).map { row -> tuple(row.meta, row.reads.collect { path -> file(path, checkIfExists: true) }) }
    selected = raw
    post_zip = channel.empty()
    trim_reports = channel.empty()
    FASTQC_RAW(raw.flatMap { meta, reads -> reads.withIndex().collect { read, i -> tuple(meta + [id: "${meta.id}.raw.R${i+1}"], read) } })
    if (params.trim_enabled.toString().toBoolean()) {
        def policy = [quality: params.trim_quality, minimum_length: params.trim_length,
            adapter: params.trim_adapter, adapter2: null]
        READ_TRIMMING(raw.map { meta, reads -> tuple(meta, reads, policy) })
        selected = READ_TRIMMING.out.artifacts
        FASTQC_POST(selected.flatMap { meta, reads -> reads.withIndex().collect { read, i -> tuple(meta + [id: "${meta.id}.post.R${i+1}"], read) } })
        post_zip = FASTQC_POST.out.artifacts
        trim_reports = READ_TRIMMING.out.reports
    }
    qc_inputs = FASTQC_RAW.out.artifacts.mix(post_zip).map { _meta, zip -> zip }
        .mix(trim_reports.map { _meta, directory -> directory }).collect()
        .map { artifacts -> tuple([id: 'fixture.multiqc', report_name: 'fixture_multiqc.html'], artifacts) }
    MULTIQC(qc_inputs)
    REFERENCE_INDEX(channel.value(tuple([id: 'fixture.index', aligner: 'bowtie2', genome_id: 'fixture_v1'],
        file(params.reference), [], [basename: 'genome', extra_args: ''])))
    inputs = selected.combine(REFERENCE_INDEX.out.artifacts).map { meta, reads, _index_meta, index ->
        tuple(meta + [aligner: 'bowtie2'], reads, file(params.reference), [], index,
            [index_basename: 'genome', extra_args: '--very-sensitive'])
    }
    ALIGNMENT(inputs)
}
