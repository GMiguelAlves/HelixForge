include { STAR_INDEX } from '../../../modules/local/star_index/main'

workflow REFERENCE_INDEX {
    take:
    index_inputs

    main:
    provider_inputs = index_inputs.map { meta, reference, annotation, index_params ->
        if (meta.aligner != 'star') {
            error "Unsupported reference-index provider: ${meta.aligner}"
        }
        tuple(meta, reference, annotation, index_params)
    }

    STAR_INDEX(provider_inputs)

    emit:
    artifacts          = STAR_INDEX.out.artifacts
    reports            = STAR_INDEX.out.reports
    versions           = STAR_INDEX.out.versions
    execution_metadata = STAR_INDEX.out.execution_metadata
    manifest           = STAR_INDEX.out.manifest
    status             = STAR_INDEX.out.status
}
