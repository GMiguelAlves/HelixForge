include { LEGACY_STEP as CHIPSEQ_PEAK_CALLING_STEP }         from '../../../modules/local/legacy_step/main'
include { LEGACY_STEP as CHIPSEQ_CONSENSUS_STEP }            from '../../../modules/local/legacy_step/main'
include { LEGACY_STEP as CHIPSEQ_DIFFERENTIAL_BINDING_STEP } from '../../../modules/local/legacy_step/main'
include { LEGACY_STEP as CHIPSEQ_ANNOTATION_STEP }           from '../../../modules/local/legacy_step/main'
include { LEGACY_STEP as CHIPSEQ_TRACKS_STEP }               from '../../../modules/local/legacy_step/main'
include { LEGACY_STEP as CHIPSEQ_REPORT_STEP }               from '../../../modules/local/legacy_step/main'

workflow CHIPSEQ_PEAK_ANALYSIS {
    take:
    config_file
    legacy_root
    reference_status
    filtered_status
    bam_qc_status

    main:
    no_dep = Channel.value('none')

    CHIPSEQ_PEAK_CALLING_STEP(
        'chipseq', 'peaks', 'high_cpu', config_file, legacy_root,
        filtered_status, no_dep, no_dep
    )
    CHIPSEQ_CONSENSUS_STEP(
        'chipseq', 'consensus', 'medium', config_file, legacy_root,
        CHIPSEQ_PEAK_CALLING_STEP.out.status, no_dep, no_dep
    )
    CHIPSEQ_DIFFERENTIAL_BINDING_STEP(
        'chipseq', 'differential', 'high_cpu', config_file, legacy_root,
        CHIPSEQ_CONSENSUS_STEP.out.status, no_dep, no_dep
    )
    CHIPSEQ_ANNOTATION_STEP(
        'chipseq', 'annotate', 'medium', config_file, legacy_root,
        CHIPSEQ_CONSENSUS_STEP.out.status, reference_status, no_dep
    )
    CHIPSEQ_TRACKS_STEP(
        'chipseq', 'tracks', 'high_cpu', config_file, legacy_root,
        filtered_status, no_dep, no_dep
    )
    CHIPSEQ_REPORT_STEP(
        'chipseq', 'report', 'medium', config_file, legacy_root,
        bam_qc_status,
        CHIPSEQ_DIFFERENTIAL_BINDING_STEP.out.status,
        CHIPSEQ_ANNOTATION_STEP.out.status.mix(CHIPSEQ_TRACKS_STEP.out.status).collect()
    )

    emit:
    status = CHIPSEQ_REPORT_STEP.out.status
    logs   = CHIPSEQ_PEAK_CALLING_STEP.out.log
        .mix(CHIPSEQ_CONSENSUS_STEP.out.log)
        .mix(CHIPSEQ_DIFFERENTIAL_BINDING_STEP.out.log)
        .mix(CHIPSEQ_ANNOTATION_STEP.out.log)
        .mix(CHIPSEQ_TRACKS_STEP.out.log)
        .mix(CHIPSEQ_REPORT_STEP.out.log)
}

