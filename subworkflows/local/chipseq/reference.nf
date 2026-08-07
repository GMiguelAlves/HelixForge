include { LEGACY_STEP as CHIPSEQ_REFERENCE_STEP } from '../../../modules/local/legacy_step/main'

workflow CHIPSEQ_REFERENCE {
    take:
    config_file
    legacy_root
    seed

    main:
    no_dep = channel.value('none')
    CHIPSEQ_REFERENCE_STEP(
        'chipseq', 'reference', 'high_memory', config_file, legacy_root,
        seed, no_dep, no_dep
    )

    emit:
    status = CHIPSEQ_REFERENCE_STEP.out.status
    logs   = CHIPSEQ_REFERENCE_STEP.out.log
}
