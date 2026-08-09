nextflow.enable.dsl = 2

include { DIFFERENTIAL_EXPRESSION } from '../../subworkflows/local/differential_expression/differential_expression'

workflow {
    repository = file("${projectDir}/../..")
    fixture = file("${repository}/tests/fixtures/native_de")
    request = channel.of(tuple(
        [id: 'golden.de', provider: 'deseq2', analysis_id: 'golden', target_dir: "${repository}/tests/results/native_de/legacy_layout"],
        file("${fixture}/import_manifest.json", checkIfExists: true),
        file("${fixture}/counts_matrix.tsv", checkIfExists: true),
        file("${fixture}/quant_samples.tsv", checkIfExists: true),
        file(params.de_analysis_spec ?: "${fixture}/analysis_spec.json", checkIfExists: true),
        file("${fixture}/annotation.gff", checkIfExists: true)
    ))
    DIFFERENTIAL_EXPRESSION(request)
}
