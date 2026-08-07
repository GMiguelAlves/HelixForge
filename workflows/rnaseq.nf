include { RNASEQ_REFERENCE }                from '../subworkflows/local/rnaseq/reference'
include { RNASEQ_QC }                       from '../subworkflows/local/rnaseq/qc'
include { RNASEQ_ALIGNMENT_QUANTIFICATION } from '../subworkflows/local/rnaseq/alignment_quantification'
include { RNASEQ_DIFFERENTIAL_EXPRESSION }  from '../subworkflows/local/rnaseq/differential_expression'

workflow RNASEQ {
    take:
    seed

    main:
    config_file = file(params.rnaseq_config, checkIfExists: true)
    legacy_root = "${projectDir}/pipelines/rnaseq/legacy"

    RNASEQ_REFERENCE(config_file, legacy_root, seed)
    RNASEQ_QC(config_file, legacy_root, seed)
    RNASEQ_ALIGNMENT_QUANTIFICATION(
        config_file,
        legacy_root,
        RNASEQ_REFERENCE.out.status,
        RNASEQ_QC.out.status,
        RNASEQ_QC.out.plans
    )
    analysis_mode = params.rnaseq_analysis_mode.toString().toLowerCase()
    if (analysis_mode == 'alignment') {
        completed_status = RNASEQ_ALIGNMENT_QUANTIFICATION.out.status
        downstream_logs = channel.empty()
    } else {
        RNASEQ_DIFFERENTIAL_EXPRESSION(
            config_file,
            legacy_root,
            RNASEQ_ALIGNMENT_QUANTIFICATION.out.status
        )
        completed_status = RNASEQ_DIFFERENTIAL_EXPRESSION.out.status
        downstream_logs = RNASEQ_DIFFERENTIAL_EXPRESSION.out.logs
    }

    emit:
    completed = completed_status
    logs      = RNASEQ_REFERENCE.out.logs
        .mix(RNASEQ_QC.out.logs)
        .mix(RNASEQ_ALIGNMENT_QUANTIFICATION.out.logs)
        .mix(downstream_logs)
}
