nextflow.enable.dsl = 2

include { RNASEQ }     from './workflows/rnaseq'
include { CHIPSEQ }    from './workflows/chipseq'
include { INTEGRATIVE } from './workflows/integrative'
include { ALL }        from './workflows/all'

workflow {
    def selected = params.workflow.toString().toLowerCase()
    def seed = channel.value('helixforge-start')

    if (selected == 'rnaseq') {
        RNASEQ(seed)
    } else if (selected == 'chipseq') {
        CHIPSEQ(seed)
    } else if (selected == 'integrative') {
        if (!params.rna_manifest || !params.chip_manifest) {
            error 'Native Integrative requires --rna_manifest and --chip_manifest'
        }
        rna_manifest = file(params.rna_manifest, checkIfExists: true)
        chip_manifest = file(params.chip_manifest, checkIfExists: true)
        rna_document = new groovy.json.JsonSlurper().parse(rna_manifest.toFile())
        chip_document = new groovy.json.JsonSlurper().parse(chip_manifest.toFile())
        rna_artifacts = file("${rna_manifest.parent}/integration_artifacts", checkIfExists: true)
        chip_artifacts = file("${chip_manifest.parent}/integration_artifacts", checkIfExists: true)
        rna_bundle = channel.value(tuple([id: rna_document.id.toString(), assay: 'rnaseq'], rna_manifest, rna_artifacts))
        chip_bundle = channel.value(tuple([id: chip_document.id.toString(), assay: 'chipseq'], chip_manifest, chip_artifacts))
        INTEGRATIVE(rna_bundle, chip_bundle)
    } else if (selected == 'all') {
        ALL(seed)
    } else {
        error "Unknown workflow '${params.workflow}'. Use rnaseq, chipseq, integrative, or all."
    }
}
