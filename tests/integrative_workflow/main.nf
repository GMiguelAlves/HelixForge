nextflow.enable.dsl = 2

include { INTEGRATIVE } from '../../workflows/integrative'

workflow {
    if (!params.rna_manifest || !params.chip_manifest) {
        error 'Provide --rna_manifest and --chip_manifest'
    }
    rna_manifest = file(params.rna_manifest, checkIfExists: true)
    chip_manifest = file(params.chip_manifest, checkIfExists: true)
    rna = new groovy.json.JsonSlurper().parse(rna_manifest.toFile())
    chip = new groovy.json.JsonSlurper().parse(chip_manifest.toFile())
    rna_bundle = channel.value(tuple([id: rna.id.toString(), assay: 'rnaseq'], rna_manifest, file("${rna_manifest.parent}/integration_artifacts", checkIfExists: true)))
    chip_bundle = channel.value(tuple([id: chip.id.toString(), assay: 'chipseq'], chip_manifest, file("${chip_manifest.parent}/integration_artifacts", checkIfExists: true)))
    INTEGRATIVE(rna_bundle, chip_bundle)
}
