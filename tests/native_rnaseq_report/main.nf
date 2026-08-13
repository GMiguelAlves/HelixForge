nextflow.enable.dsl = 2

include { RNASEQ_REPORT } from '../../subworkflows/local/rnaseq/report'

workflow {
    fixture = file("${projectDir}/../fixtures/native_rnaseq_report")
    parameters = groovy.json.JsonOutput.toJson([
        title: 'Stub candidate gene report', expression_unit: 'TPM',
        life_stage_levels: 'unknown', stage_synonym_map: '', organism_specific: false
    ]).getBytes('UTF-8').encodeBase64().toString()
    meta = [
        id: 'stub.rnaseq.report', provider: 'candidate_genes_v1',
        target_dir: "${params.outdir}/rnaseq/090-search-gene"
    ]
    request = channel.of(tuple(
        meta,
        file("${fixture}/import_manifest.json", checkIfExists: true),
        file("${fixture}/tpm_matrix.tsv", checkIfExists: true),
        file("${fixture}/quant_samples.tsv", checkIfExists: true),
        file("${fixture}/annotation.gtf", checkIfExists: true),
        file("${fixture}/DEGs_all_results.tsv", checkIfExists: true),
        file("${fixture}/de_manifest.json", checkIfExists: true),
        file("${fixture}/genes.txt", checkIfExists: true),
        parameters
    ))
    RNASEQ_REPORT(request)
}
