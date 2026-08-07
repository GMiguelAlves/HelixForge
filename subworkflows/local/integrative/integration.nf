include { LEGACY_STEP as INTEGRATIVE_VALIDATE_STEP }       from '../../../modules/local/legacy_step/main'
include { LEGACY_STEP as INTEGRATIVE_PREPARE_STEP }        from '../../../modules/local/legacy_step/main'
include { LEGACY_STEP as INTEGRATIVE_HARMONIZE_STEP }      from '../../../modules/local/legacy_step/main'
include { LEGACY_STEP as INTEGRATIVE_MAP_PEAKS_STEP }      from '../../../modules/local/legacy_step/main'
include { LEGACY_STEP as INTEGRATIVE_SUMMARIZE_RNA_STEP }  from '../../../modules/local/legacy_step/main'
include { LEGACY_STEP as INTEGRATIVE_SUMMARIZE_CHIP_STEP } from '../../../modules/local/legacy_step/main'
include { LEGACY_STEP as INTEGRATIVE_INTEGRATE_STEP }      from '../../../modules/local/legacy_step/main'
include { LEGACY_STEP as INTEGRATIVE_SCORE_STEP }          from '../../../modules/local/legacy_step/main'
include { LEGACY_STEP as INTEGRATIVE_VISUALIZE_STEP }      from '../../../modules/local/legacy_step/main'
include { LEGACY_STEP as INTEGRATIVE_FUNCTIONAL_STEP }     from '../../../modules/local/legacy_step/main'
include { LEGACY_STEP as INTEGRATIVE_REPORT_STEP }         from '../../../modules/local/legacy_step/main'

workflow INTEGRATION {
    take:
    config_file
    legacy_root
    seed

    main:
    no_dep = channel.value('none')

    INTEGRATIVE_VALIDATE_STEP('integrative', 'validate', 'low', config_file, legacy_root, seed, no_dep, no_dep)
    INTEGRATIVE_PREPARE_STEP('integrative', 'prepare', 'medium', config_file, legacy_root, INTEGRATIVE_VALIDATE_STEP.out.status, no_dep, no_dep)
    INTEGRATIVE_HARMONIZE_STEP('integrative', 'harmonize', 'medium', config_file, legacy_root, INTEGRATIVE_PREPARE_STEP.out.status, no_dep, no_dep)
    INTEGRATIVE_MAP_PEAKS_STEP('integrative', 'map-peaks', 'medium', config_file, legacy_root, INTEGRATIVE_HARMONIZE_STEP.out.status, no_dep, no_dep)
    INTEGRATIVE_SUMMARIZE_RNA_STEP(
        'integrative', 'summarize-rna', 'medium', config_file, legacy_root,
        INTEGRATIVE_PREPARE_STEP.out.status, INTEGRATIVE_HARMONIZE_STEP.out.status, no_dep
    )
    INTEGRATIVE_SUMMARIZE_CHIP_STEP(
        'integrative', 'summarize-chip', 'medium', config_file, legacy_root,
        INTEGRATIVE_MAP_PEAKS_STEP.out.status, no_dep, no_dep
    )
    INTEGRATIVE_INTEGRATE_STEP(
        'integrative', 'integrate', 'medium', config_file, legacy_root,
        INTEGRATIVE_SUMMARIZE_RNA_STEP.out.status,
        INTEGRATIVE_SUMMARIZE_CHIP_STEP.out.status,
        no_dep
    )
    INTEGRATIVE_SCORE_STEP('integrative', 'score', 'medium', config_file, legacy_root, INTEGRATIVE_INTEGRATE_STEP.out.status, no_dep, no_dep)
    INTEGRATIVE_VISUALIZE_STEP('integrative', 'visualize', 'medium', config_file, legacy_root, INTEGRATIVE_SCORE_STEP.out.status, no_dep, no_dep)
    INTEGRATIVE_FUNCTIONAL_STEP('integrative', 'functional', 'medium', config_file, legacy_root, INTEGRATIVE_SCORE_STEP.out.status, no_dep, no_dep)
    INTEGRATIVE_REPORT_STEP(
        'integrative', 'report', 'medium', config_file, legacy_root,
        INTEGRATIVE_VISUALIZE_STEP.out.status,
        INTEGRATIVE_FUNCTIONAL_STEP.out.status,
        no_dep
    )

    emit:
    status = INTEGRATIVE_REPORT_STEP.out.status
    logs   = INTEGRATIVE_VALIDATE_STEP.out.log
        .mix(INTEGRATIVE_PREPARE_STEP.out.log)
        .mix(INTEGRATIVE_HARMONIZE_STEP.out.log)
        .mix(INTEGRATIVE_MAP_PEAKS_STEP.out.log)
        .mix(INTEGRATIVE_SUMMARIZE_RNA_STEP.out.log)
        .mix(INTEGRATIVE_SUMMARIZE_CHIP_STEP.out.log)
        .mix(INTEGRATIVE_INTEGRATE_STEP.out.log)
        .mix(INTEGRATIVE_SCORE_STEP.out.log)
        .mix(INTEGRATIVE_VISUALIZE_STEP.out.log)
        .mix(INTEGRATIVE_FUNCTIONAL_STEP.out.log)
        .mix(INTEGRATIVE_REPORT_STEP.out.log)
}
