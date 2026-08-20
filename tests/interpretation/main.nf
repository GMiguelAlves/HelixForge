nextflow.enable.dsl = 2

include { EVIDENCE_HARMONIZATION } from '../../modules/local/evidence_harmonization/main'
include { MOLECULAR_EVIDENCE_INTEGRATION } from '../../modules/local/molecular_evidence_integration/main'
include { REGULATORY_INTERPRETATION } from '../../modules/local/regulatory_interpretation/main'
include { CANDIDATE_SCORING } from '../../modules/local/candidate_scoring/main'
include { CROSS_ASSAY_STATISTICS } from '../../modules/local/cross_assay_statistics/main'

workflow {
    if (!params.rna_evidence || !params.chip_evidence) {
        error 'Provide --rna_evidence and --chip_evidence fixture directories'
    }
    rna = file(params.rna_evidence, checkIfExists: true)
    chip = file(params.chip_evidence, checkIfExists: true)
    harmonization_policy = file(params.harmonization_policy, checkIfExists: true)
    interpretation_policy = file(params.interpretation_policy, checkIfExists: true)
    mark_roles = file(params.mark_roles, checkIfExists: true)
    context = file(params.prioritization_context, checkIfExists: true)
    meta = [id: 'fixture.interpretation']

    EVIDENCE_HARMONIZATION(channel.of(tuple(meta, rna, chip, harmonization_policy)))
    integration_input = EVIDENCE_HARMONIZATION.out.artifacts.map { item_meta, harmonization -> tuple(item_meta, rna, chip, harmonization) }
    MOLECULAR_EVIDENCE_INTEGRATION(integration_input)

    regulatory_input = MOLECULAR_EVIDENCE_INTEGRATION.out.artifacts.map { item_meta, integration -> tuple(item_meta, integration, interpretation_policy, mark_roles) }
    REGULATORY_INTERPRETATION(regulatory_input)

    integration_and_classes = MOLECULAR_EVIDENCE_INTEGRATION.out.artifacts.join(REGULATORY_INTERPRETATION.out.artifacts)
    scoring_input = integration_and_classes.map { item_meta, integration, classification -> tuple(item_meta, integration, classification, interpretation_policy, context) }
    CANDIDATE_SCORING(scoring_input)

    final_input = integration_and_classes.join(CANDIDATE_SCORING.out.artifacts).map { item_meta, integration, classification, scoring ->
        tuple(item_meta, integration, classification, scoring, interpretation_policy, mark_roles, context)
    }
    CROSS_ASSAY_STATISTICS(final_input)
}
