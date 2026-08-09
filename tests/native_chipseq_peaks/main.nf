nextflow.enable.dsl = 2

include { PEAK_CALLING_CONTEXT } from '../../modules/local/peak_calling_context/main'
include { PEAK_CALLING } from '../../subworkflows/local/chipseq/peak_calling'

workflow {
    fixture = file(params.fixture_dir, checkIfExists: true)
    plan = file("${fixture}/chipseq_plan.tsv", checkIfExists: true)
    spec = [
        caller: params.caller,
        caller_version: '3.0.4',
        peak_type: params.peak_type,
        effective_genome_size: params.effective_genome_size,
        q_value: params.q_value,
        p_value: params.p_value,
        format: null,
        duplicate_policy: 'all',
        additional_args: null,
        output_dir: "${params.outdir}/peaks",
    ]
    spec_base64 = groovy.json.JsonOutput.toJson(spec).getBytes('UTF-8').encodeBase64().toString()
    PEAK_CALLING_CONTEXT(channel.of(tuple([id: 'fixture.peak-context'], plan, spec_base64)))

    ids = ['input_rep1', 'chip_rep1', 'chip_rep2']
    final_bams = channel.fromList(ids).map { id ->
        def is_control = id == 'input_rep1'
        tuple(
            [id: id, sample_id: id, dataset: 'fixture', is_control: is_control, genome_id: 'fixture_v1'],
            file("${fixture}/${id}.filtered.bam", checkIfExists: true),
            file("${fixture}/${id}.filtered.bam.bai", checkIfExists: true)
        )
    }
    final_manifests = channel.fromList(ids).map { id ->
        tuple([id: id], file("${fixture}/${id}.manifest.json", checkIfExists: true))
    }
    PEAK_CALLING(final_bams, final_manifests, PEAK_CALLING_CONTEXT.out.artifacts)
}
