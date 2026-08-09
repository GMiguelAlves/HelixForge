include { STAR_INDEX } from '../../../modules/local/star_index/main'
include { BOWTIE2_INDEX } from '../../../modules/local/bowtie2_index/main'

workflow REFERENCE_INDEX {
    take:
    index_inputs

    main:
    provider_inputs = index_inputs.map { meta, reference, annotation, index_params ->
        if (!(meta.aligner in ['star', 'bowtie2'])) {
            error "Unsupported reference-index provider: ${meta.aligner}"
        }
        tuple(meta, reference, annotation, index_params)
    }

    star_inputs = provider_inputs.filter { meta, _reference, _annotation, _params -> meta.aligner == 'star' }
    bowtie2_inputs = provider_inputs.filter { meta, _reference, _annotation, _params -> meta.aligner == 'bowtie2' }

    STAR_INDEX(star_inputs)
    BOWTIE2_INDEX(bowtie2_inputs)

    emit:
    artifacts          = STAR_INDEX.out.artifacts.mix(BOWTIE2_INDEX.out.artifacts)
    reports            = STAR_INDEX.out.reports.mix(BOWTIE2_INDEX.out.reports)
    versions           = STAR_INDEX.out.versions.mix(BOWTIE2_INDEX.out.versions)
    execution_metadata = STAR_INDEX.out.execution_metadata.mix(BOWTIE2_INDEX.out.execution_metadata)
    manifest           = STAR_INDEX.out.manifest.mix(BOWTIE2_INDEX.out.manifest)
    status             = STAR_INDEX.out.status.mix(BOWTIE2_INDEX.out.status)
}
