nextflow.enable.dsl = 2

include { CHIPSEQ_REPORT } from '../../subworkflows/local/chipseq/report'

def resolve_location(inventory_file, value) {
    def candidate = java.nio.file.Paths.get(value.toString())
    candidate.isAbsolute() ? value.toString() : "${inventory_file.parent}/${value}"
}

workflow {
    inventory_file = file(params.report_inventory, checkIfExists: true)
    inventory = new groovy.json.JsonSlurper().parse(inventory_file.toFile())
    manifests = inventory.components.collect { entry -> file(resolve_location(inventory_file, entry.manifest), checkIfExists: true) }
    artifacts = inventory.components.collectMany { entry -> (entry.artifacts ?: []).collect { value -> file(resolve_location(inventory_file, value), checkIfExists: true) } }
    meta = [id: 'fixture_project.chipseq_report', project_id: 'fixture_project', dataset: 'fixture_dataset', genome_id: 'fixture_v1', build: 'fixture_v1']
    presentation = [provider: 'html_v1', title: 'Fixture ChIP-seq report', language: 'en']
    encoded = groovy.json.JsonOutput.toJson(presentation).getBytes('UTF-8').encodeBase64().toString()
    CHIPSEQ_REPORT(channel.value(tuple(meta, inventory_file, manifests, artifacts, encoded)))
}
