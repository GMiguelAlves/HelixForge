include { LEGACY_STEP as RNASEQ_BATCH_STEP }  from '../../../modules/local/legacy_step/main'
include { LEGACY_STEP as RNASEQ_DEG_STEP }    from '../../../modules/local/legacy_step/main'
include { LEGACY_STEP as RNASEQ_REPORT_STEP } from '../../../modules/local/legacy_step/main'

workflow RNASEQ_DIFFERENTIAL_EXPRESSION {
    take:
    config_file
    legacy_root
    quantification_status

    main:
    no_dep = channel.value('none')

    // batch and report are skipped by the compatibility wrapper when their
    // existing RUN_* flags are disabled in pipeline_config.sh.
    RNASEQ_BATCH_STEP(
        'rnaseq', 'batch', 'medium', config_file, legacy_root,
        quantification_status, no_dep, no_dep
    )
    RNASEQ_DEG_STEP(
        'rnaseq', 'deg', 'high_cpu', config_file, legacy_root,
        RNASEQ_BATCH_STEP.out.status, no_dep, no_dep
    )
    RNASEQ_REPORT_STEP(
        'rnaseq', 'report', 'medium', config_file, legacy_root,
        RNASEQ_DEG_STEP.out.status, no_dep, no_dep
    )

    emit:
    status = RNASEQ_REPORT_STEP.out.status
    logs   = RNASEQ_BATCH_STEP.out.log
        .mix(RNASEQ_DEG_STEP.out.log)
        .mix(RNASEQ_REPORT_STEP.out.log)
}
