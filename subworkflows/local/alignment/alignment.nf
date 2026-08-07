include { STAR_ALIGN } from '../../../modules/local/star_align/main'

workflow ALIGNMENT {
    take:
    alignment_inputs

    main:
    provider_inputs = alignment_inputs.map { meta, reads, reference, annotation, index, alignment_params ->
        if (meta.aligner != 'star') {
            error "Unsupported alignment provider: ${meta.aligner}"
        }
        tuple(meta, reads, reference, annotation, index, alignment_params)
    }

    STAR_ALIGN(provider_inputs)

    aligned_bam_ch = STAR_ALIGN.out.artifacts.map { meta, bam, _bai -> tuple(meta, bam) }
    bam_index_ch = STAR_ALIGN.out.artifacts.map { meta, _bam, bai -> tuple(meta, bai) }
    logs_ch = STAR_ALIGN.out.reports.map { meta, logs, _statistics -> tuple(meta, logs) }
    statistics_ch = STAR_ALIGN.out.reports.map { meta, _logs, statistics -> tuple(meta, statistics) }

    emit:
    aligned_bam        = aligned_bam_ch
    bam_index          = bam_index_ch
    logs               = logs_ch
    statistics         = statistics_ch
    versions           = STAR_ALIGN.out.versions
    execution_metadata = STAR_ALIGN.out.execution_metadata
    manifest           = STAR_ALIGN.out.manifest
    status             = STAR_ALIGN.out.status
    artifacts          = STAR_ALIGN.out.artifacts
    reports            = STAR_ALIGN.out.reports
}
