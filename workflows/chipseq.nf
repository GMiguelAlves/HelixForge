include { CHIPSEQ_REFERENCE }    from '../subworkflows/local/chipseq/reference'
include { CHIPSEQ_QC_ALIGNMENT } from '../subworkflows/local/chipseq/qc_alignment'
include { CHIPSEQ_PEAK_ANALYSIS } from '../subworkflows/local/chipseq/peak_analysis'

workflow CHIPSEQ {
    take:
    seed

    main:
    config_file = file(params.chipseq_config, checkIfExists: true)
    legacy_root = "${projectDir}/pipelines/chipseq/legacy"

    CHIPSEQ_REFERENCE(config_file, legacy_root, seed)
    CHIPSEQ_QC_ALIGNMENT(config_file, legacy_root, CHIPSEQ_REFERENCE.out.status, seed)
    CHIPSEQ_PEAK_ANALYSIS(
        config_file,
        legacy_root,
        CHIPSEQ_REFERENCE.out.status,
        CHIPSEQ_QC_ALIGNMENT.out.filtered,
        CHIPSEQ_QC_ALIGNMENT.out.status
    )

    emit:
    completed = CHIPSEQ_PEAK_ANALYSIS.out.status
    logs      = CHIPSEQ_REFERENCE.out.logs
        .mix(CHIPSEQ_QC_ALIGNMENT.out.logs)
        .mix(CHIPSEQ_PEAK_ANALYSIS.out.logs)
}

