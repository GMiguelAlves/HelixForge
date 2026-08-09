include { CHIPSEQ_REFERENCE }    from '../subworkflows/local/chipseq/reference'
include { CHIPSEQ_QC_ALIGNMENT } from '../subworkflows/local/chipseq/qc_alignment'
include { CHIPSEQ_PEAK_ANALYSIS } from '../subworkflows/local/chipseq/peak_analysis'
include { CHIPSEQ_NATIVE_FOUNDATION } from '../subworkflows/local/chipseq/native_foundation'

workflow CHIPSEQ {
    take:
    seed

    main:
    config_file = file(params.chipseq_config, checkIfExists: true)
    legacy_root = "${projectDir}/pipelines/chipseq/legacy"
    run_mode = params.chipseq_run_mode.toString().toLowerCase()
    if (!(run_mode in ['qc', 'alignment', 'peaks', 'full'])) {
        error "Unknown chipseq_run_mode '${params.chipseq_run_mode}'. Use qc, alignment, peaks, or full."
    }

    if (params.chipseq_native_foundation && run_mode in ['qc', 'alignment']) {
        CHIPSEQ_NATIVE_FOUNDATION(config_file, legacy_root, seed)
        completed_ch = CHIPSEQ_NATIVE_FOUNDATION.out.completed
        logs_ch = CHIPSEQ_NATIVE_FOUNDATION.out.logs
    } else {
        CHIPSEQ_REFERENCE(config_file, legacy_root, seed)
        CHIPSEQ_QC_ALIGNMENT(config_file, legacy_root, CHIPSEQ_REFERENCE.out.status, seed)
        CHIPSEQ_PEAK_ANALYSIS(
            config_file,
            legacy_root,
            CHIPSEQ_REFERENCE.out.status,
            CHIPSEQ_QC_ALIGNMENT.out.filtered,
            CHIPSEQ_QC_ALIGNMENT.out.status
        )
        completed_ch = CHIPSEQ_PEAK_ANALYSIS.out.status
        logs_ch = CHIPSEQ_REFERENCE.out.logs
            .mix(CHIPSEQ_QC_ALIGNMENT.out.logs)
            .mix(CHIPSEQ_PEAK_ANALYSIS.out.logs)
    }

    emit:
    completed = completed_ch
    logs      = logs_ch
}
