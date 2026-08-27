nextflow.enable.dsl = 2

include { RNASEQ_REPORT } from '../../../subworkflows/local/rnaseq/report'

workflow {
    report_parameters = [
        title              : params.report_title,
        expression_unit    : 'TPM',
        life_stage_levels  : 'unknown',
        stage_synonym_map  : '',
        organism_specific : false
    ]
    report_parameters_base64 = groovy.json.JsonOutput.toJson(report_parameters)
        .bytes.encodeBase64().toString()
    meta = [
        id         : 'rnaseq.report.candidate_genes',
        provider   : 'candidate_genes_v1',
        target_dir : params.report_target,
        import_id  : 'rnaseq.import',
        analysis_id: 'benchmark_airway_primary'
    ]
    requests = channel.of(tuple(
        meta,
        file(params.import_manifest, checkIfExists: true),
        file(params.abundance, checkIfExists: true),
        file(params.samples, checkIfExists: true),
        file(params.annotation, checkIfExists: true),
        file(params.de_results, checkIfExists: true),
        file(params.de_manifest, checkIfExists: true),
        file(params.genes, checkIfExists: true),
        report_parameters_base64
    ))
    RNASEQ_REPORT(requests)
}
