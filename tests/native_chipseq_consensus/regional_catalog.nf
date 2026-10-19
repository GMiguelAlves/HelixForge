nextflow.enable.dsl = 2

include { REGIONAL_CATALOG } from '../../modules/local/regional_catalog/main'
params.request = null
params.program = null

workflow {
    repo = file(params.repo_root, checkIfExists: true)
    caseRoot = file(params.case_root, checkIfExists: true)
    request = file(params.request ?: "${caseRoot}/request.json", checkIfExists: true)
    program = file(params.program ?: "${repo}/modules/local/regional_catalog/resources/usr/bin/run_regional_catalog.py", checkIfExists: true)
    dirs = (1..3).collect { i -> file("${caseRoot}/ip${i}.peak_calling", checkIfExists: true) }
    document = new groovy.json.JsonSlurper().parse(request.toFile())
    meta = [id: document.id, dataset: 'independent_synthetic', condition: 'balanced', target: 'synthetic_broad', genome_id: 'regional_validation_v1']
    REGIONAL_CATALOG(channel.of(tuple(meta, dirs, request, program)))
}
