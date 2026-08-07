include { LEGACY_STEP as CHIPSEQ_QC_STEP }        from '../../../modules/local/legacy_step/main'
include { LEGACY_STEP as CHIPSEQ_TRIM_STEP }      from '../../../modules/local/legacy_step/main'
include { LEGACY_STEP as CHIPSEQ_ALIGNMENT_STEP } from '../../../modules/local/legacy_step/main'
include { LEGACY_STEP as CHIPSEQ_FILTER_STEP }    from '../../../modules/local/legacy_step/main'
include { LEGACY_STEP as CHIPSEQ_BAM_QC_STEP }    from '../../../modules/local/legacy_step/main'

workflow CHIPSEQ_QC_ALIGNMENT {
    take:
    config_file
    legacy_root
    reference_status
    seed

    main:
    no_dep = Channel.value('none')

    CHIPSEQ_QC_STEP(
        'chipseq', 'qc', 'medium', config_file, legacy_root,
        seed, no_dep, no_dep
    )
    CHIPSEQ_TRIM_STEP(
        'chipseq', 'trim', 'high_cpu', config_file, legacy_root,
        CHIPSEQ_QC_STEP.out.status, no_dep, no_dep
    )
    CHIPSEQ_ALIGNMENT_STEP(
        'chipseq', 'align', 'high_cpu', config_file, legacy_root,
        CHIPSEQ_TRIM_STEP.out.status, reference_status, no_dep
    )
    CHIPSEQ_FILTER_STEP(
        'chipseq', 'filter', 'high_cpu', config_file, legacy_root,
        CHIPSEQ_ALIGNMENT_STEP.out.status, no_dep, no_dep
    )
    CHIPSEQ_BAM_QC_STEP(
        'chipseq', 'bam_qc', 'medium', config_file, legacy_root,
        CHIPSEQ_FILTER_STEP.out.status, no_dep, no_dep
    )

    emit:
    filtered = CHIPSEQ_FILTER_STEP.out.status
    status   = CHIPSEQ_BAM_QC_STEP.out.status
    logs     = CHIPSEQ_QC_STEP.out.log
        .mix(CHIPSEQ_TRIM_STEP.out.log)
        .mix(CHIPSEQ_ALIGNMENT_STEP.out.log)
        .mix(CHIPSEQ_FILTER_STEP.out.log)
        .mix(CHIPSEQ_BAM_QC_STEP.out.log)
}

