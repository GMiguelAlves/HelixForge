include { STAR_INDEX } from '../../../modules/local/star_index/main'
include { BOWTIE2_INDEX } from '../../../modules/local/bowtie2_index/main'
include { BOWTIE2_INDEX_VALIDATE } from '../../../modules/local/bowtie2_index_validate/main'

workflow REFERENCE_INDEX {
    take:
    index_inputs

    main:
    provider_inputs = index_inputs.map { meta, reference, annotation, index_params ->
        if (!(meta.aligner in ['star', 'bowtie2'])) {
            error "Unsupported reference-index provider: ${meta.aligner}"
        }
        if ((index_params.prebuilt_index != null) != (index_params.prebuilt_manifest != null)) {
            error 'Prebuilt index directory and manifest must be supplied together'
        }
        if (meta.aligner != 'bowtie2' && index_params.prebuilt_index != null) {
            error 'Prebuilt reference-index dispatch is currently implemented only for Bowtie2'
        }
        tuple(meta, reference, annotation, index_params)
    }

    star_inputs = provider_inputs.filter { meta, _reference, _annotation, _params -> meta.aligner == 'star' }
    bowtie2_inputs = provider_inputs.filter { meta, _reference, _annotation, _params -> meta.aligner == 'bowtie2' }

    STAR_INDEX(star_inputs)
    build_inputs = bowtie2_inputs.filter { _meta, _reference, _annotation, p -> p.prebuilt_index == null }
    reuse_inputs = bowtie2_inputs
        .filter { _meta, _reference, _annotation, p -> p.prebuilt_index != null }
        .map { meta, reference, _annotation, p ->
            tuple(meta, reference, file(p.prebuilt_index, checkIfExists: true), file(p.prebuilt_manifest, checkIfExists: true),
                [basename: p.basename ?: 'genome', extra_args: p.extra_args ?: ''])
        }
    BOWTIE2_INDEX(build_inputs)
    BOWTIE2_INDEX_VALIDATE(reuse_inputs)

    emit:
    artifacts          = STAR_INDEX.out.artifacts.mix(BOWTIE2_INDEX.out.artifacts).mix(BOWTIE2_INDEX_VALIDATE.out.artifacts)
    reports            = STAR_INDEX.out.reports.mix(BOWTIE2_INDEX.out.reports).mix(BOWTIE2_INDEX_VALIDATE.out.reports)
    versions           = STAR_INDEX.out.versions.mix(BOWTIE2_INDEX.out.versions).mix(BOWTIE2_INDEX_VALIDATE.out.versions)
    execution_metadata = STAR_INDEX.out.execution_metadata.mix(BOWTIE2_INDEX.out.execution_metadata).mix(BOWTIE2_INDEX_VALIDATE.out.execution_metadata)
    manifest           = STAR_INDEX.out.manifest.mix(BOWTIE2_INDEX.out.manifest).mix(BOWTIE2_INDEX_VALIDATE.out.manifest)
    status             = STAR_INDEX.out.status.mix(BOWTIE2_INDEX.out.status).mix(BOWTIE2_INDEX_VALIDATE.out.status)
}
