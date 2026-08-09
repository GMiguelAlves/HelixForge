include { STAR_ALIGN } from '../../../modules/local/star_align/main'
include { BOWTIE2_ALIGN } from '../../../modules/local/bowtie2_align/main'

workflow ALIGNMENT {
    take:
    alignment_inputs

    main:
    provider_inputs = alignment_inputs.map { meta, reads, reference, annotation, index, alignment_params ->
        if (!(meta.aligner in ['star', 'bowtie2'])) {
            error "Unsupported alignment provider: ${meta.aligner}"
        }
        tuple(meta, reads, reference, annotation, index, alignment_params)
    }

    star_inputs = provider_inputs.filter { meta, _reads, _reference, _annotation, _index, _params -> meta.aligner == 'star' }
    bowtie2_inputs = provider_inputs.filter { meta, _reads, _reference, _annotation, _index, _params -> meta.aligner == 'bowtie2' }

    STAR_ALIGN(star_inputs)
    BOWTIE2_ALIGN(bowtie2_inputs)

    artifacts_ch = STAR_ALIGN.out.artifacts.mix(BOWTIE2_ALIGN.out.artifacts)
    reports_ch = STAR_ALIGN.out.reports.mix(BOWTIE2_ALIGN.out.reports)
    aligned_bam_ch = artifacts_ch.map { meta, bam, _bai -> tuple(meta, bam) }
    bam_index_ch = artifacts_ch.map { meta, _bam, bai -> tuple(meta, bai) }
    logs_ch = reports_ch.map { meta, logs, _statistics -> tuple(meta, logs) }
    statistics_ch = reports_ch.map { meta, _logs, statistics -> tuple(meta, statistics) }
    gene_counts_ch = STAR_ALIGN.out.reports.map { meta, _logs, statistics ->
        tuple(meta, statistics.resolve('ReadsPerGene.out.tab'))
    }

    emit:
    aligned_bam        = aligned_bam_ch
    bam_index          = bam_index_ch
    logs               = logs_ch
    statistics         = statistics_ch
    gene_counts         = gene_counts_ch
    versions           = STAR_ALIGN.out.versions.mix(BOWTIE2_ALIGN.out.versions)
    execution_metadata = STAR_ALIGN.out.execution_metadata.mix(BOWTIE2_ALIGN.out.execution_metadata)
    manifest           = STAR_ALIGN.out.manifest.mix(BOWTIE2_ALIGN.out.manifest)
    status             = STAR_ALIGN.out.status.mix(BOWTIE2_ALIGN.out.status)
    artifacts          = artifacts_ch
    reports            = reports_ch
}
