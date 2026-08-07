include { LEGACY_STEP as RNASEQ_DOWNLOAD_STEP } from '../../../modules/local/legacy_step/main'
include { LEGACY_STEP as RNASEQ_METADATA_STEP } from '../../../modules/local/legacy_step/main'
include { LEGACY_STEP as RNASEQ_QC_STEP }       from '../../../modules/local/legacy_step/main'

workflow RNASEQ_QC {
    take:
    config_file
    legacy_root
    seed

    main:
    no_dep = channel.value('none')

    RNASEQ_DOWNLOAD_STEP(
        'rnaseq', 'download', 'medium', config_file, legacy_root,
        seed, no_dep, no_dep
    )
    RNASEQ_METADATA_STEP(
        'rnaseq', 'metadata', 'medium', config_file, legacy_root,
        seed, no_dep, no_dep
    )
    RNASEQ_QC_STEP(
        'rnaseq', 'qc', 'high_cpu', config_file, legacy_root,
        RNASEQ_DOWNLOAD_STEP.out.status,
        RNASEQ_METADATA_STEP.out.status,
        no_dep
    )

    emit:
    status = RNASEQ_QC_STEP.out.status
    logs   = RNASEQ_DOWNLOAD_STEP.out.log
        .mix(RNASEQ_METADATA_STEP.out.log)
        .mix(RNASEQ_QC_STEP.out.log)
}
