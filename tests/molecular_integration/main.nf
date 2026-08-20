nextflow.enable.dsl = 2

include { EVIDENCE_HARMONIZATION } from '../../modules/local/evidence_harmonization/main'
include { MOLECULAR_EVIDENCE_INTEGRATION } from '../../modules/local/molecular_evidence_integration/main'

workflow {
    if (!params.rna_evidence || !params.chip_evidence) {
        error 'Provide --rna_evidence and --chip_evidence fixture directories'
    }
    rna = file(params.rna_evidence, checkIfExists: true)
    chip = file(params.chip_evidence, checkIfExists: true)
    policy = file(params.harmonization_policy, checkIfExists: true)

    harmonization_input = channel.of(tuple([id: 'fixture.cross_assay'], rna, chip, policy))
    EVIDENCE_HARMONIZATION(harmonization_input)

    integration_input = EVIDENCE_HARMONIZATION.out.artifacts.map { _meta, harmonization ->
        tuple([id: 'fixture.master_evidence'], rna, chip, harmonization)
    }
    MOLECULAR_EVIDENCE_INTEGRATION(integration_input)
}
