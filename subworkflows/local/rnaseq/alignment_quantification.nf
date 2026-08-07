include { LEGACY_STEP as RNASEQ_ALIGNMENT_STEP }      from '../../../modules/local/legacy_step/main'
include { LEGACY_STEP as RNASEQ_QUANTIFICATION_STEP } from '../../../modules/local/legacy_step/main'

workflow RNASEQ_ALIGNMENT_QUANTIFICATION {
    take:
    config_file
    legacy_root
    reference_status
    qc_status

    main:
    no_dep = Channel.value('none')

    // The legacy "salmon" coarse step chooses Salmon or STAR from
    // QUANT_METHOD in pipeline_config.sh.
    RNASEQ_ALIGNMENT_STEP(
        'rnaseq', 'salmon', 'high_cpu', config_file, legacy_root,
        reference_status, qc_status, no_dep
    )
    RNASEQ_QUANTIFICATION_STEP(
        'rnaseq', 'tximport', 'medium', config_file, legacy_root,
        RNASEQ_ALIGNMENT_STEP.out.status, no_dep, no_dep
    )

    emit:
    status = RNASEQ_QUANTIFICATION_STEP.out.status
    logs   = RNASEQ_ALIGNMENT_STEP.out.log.mix(RNASEQ_QUANTIFICATION_STEP.out.log)
}

