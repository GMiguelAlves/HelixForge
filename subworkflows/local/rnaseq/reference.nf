include { LEGACY_STEP as RNASEQ_REFERENCE_STEP } from '../../../modules/local/legacy_step/main'

workflow RNASEQ_REFERENCE {
    take:
    config_file
    legacy_root
    seed

    main:
    no_dep = Channel.value('none')
    RNASEQ_REFERENCE_STEP(
        'rnaseq', 'reference', 'high_memory', config_file, legacy_root,
        seed, no_dep, no_dep
    )

    emit:
    status = RNASEQ_REFERENCE_STEP.out.status
    logs   = RNASEQ_REFERENCE_STEP.out.log
}

