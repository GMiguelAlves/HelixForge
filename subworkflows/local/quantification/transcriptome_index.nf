include { SALMON_INDEX } from '../../../modules/local/salmon_index/main'

workflow TRANSCRIPTOME_INDEX {
    take:
    index_inputs

    main:
    provider_inputs = index_inputs.map { meta, transcriptome, index_params ->
        if (meta.quantifier != 'salmon') {
            error "Unsupported transcriptome-index provider: ${meta.quantifier}"
        }
        tuple(meta, transcriptome, index_params)
    }

    SALMON_INDEX(provider_inputs)

    emit:
    artifacts          = SALMON_INDEX.out.artifacts
    reports            = SALMON_INDEX.out.reports
    versions           = SALMON_INDEX.out.versions
    execution_metadata = SALMON_INDEX.out.execution_metadata
    manifest           = SALMON_INDEX.out.manifest
    status             = SALMON_INDEX.out.status
}
