include { CHIPSEQ_REFERENCE }    from '../subworkflows/local/chipseq/reference'
include { CHIPSEQ_QC_ALIGNMENT } from '../subworkflows/local/chipseq/qc_alignment'
include { CHIPSEQ_PEAK_ANALYSIS } from '../subworkflows/local/chipseq/peak_analysis'
include { CHIPSEQ_NATIVE_FOUNDATION } from '../subworkflows/local/chipseq/native_foundation'
include { LEGACY_STEP as CHIPSEQ_LEGACY_PEAKS } from '../modules/local/legacy_step/main'
include { LEGACY_STEP as CHIPSEQ_LEGACY_CONSENSUS } from '../modules/local/legacy_step/main'
include { LEGACY_STEP as CHIPSEQ_LEGACY_DIFFERENTIAL } from '../modules/local/legacy_step/main'

workflow CHIPSEQ {
    take:
    seed

    main:
    config_file = file(params.chipseq_config, checkIfExists: true)
    legacy_root = "${projectDir}/pipelines/chipseq/legacy"
    run_mode = params.chipseq_run_mode.toString().toLowerCase()
    native_peak_calling = params.chipseq_native_peak_calling.toString().toBoolean()
    native_peak_qc = params.chipseq_native_peak_qc.toString().toBoolean()
    native_consensus = params.chipseq_native_consensus.toString().toBoolean()
    native_differential = params.chipseq_native_differential_binding.toString().toBoolean()
    if (!(run_mode in ['qc', 'alignment', 'post_alignment', 'peaks', 'peak_qc', 'consensus', 'idr', 'differential_binding', 'full'])) {
        error "Unknown chipseq_run_mode '${params.chipseq_run_mode}'. Use qc, alignment, post_alignment, peaks, peak_qc, consensus, idr, differential_binding, or full."
    }

    native_mode = params.chipseq_native_foundation && (
        run_mode in ['qc', 'alignment', 'post_alignment'] ||
        (run_mode in ['peaks', 'peak_qc'] && native_peak_calling) ||
        (run_mode in ['consensus', 'idr'] && native_peak_calling && native_peak_qc && native_consensus) ||
        (run_mode == 'differential_binding' && native_peak_calling && native_peak_qc && native_consensus && native_differential)
    )

    if (native_mode) {
        CHIPSEQ_NATIVE_FOUNDATION(config_file, legacy_root, seed)
        if (run_mode == 'post_alignment' && params.chipseq_continue_legacy_peaks) {
            no_dep = channel.value('none')
            CHIPSEQ_LEGACY_PEAKS(
                'chipseq', 'peaks', 'high_cpu', config_file, legacy_root,
                CHIPSEQ_NATIVE_FOUNDATION.out.completed.collect(), no_dep, no_dep
            )
            completed_ch = CHIPSEQ_LEGACY_PEAKS.out.status
            logs_ch = CHIPSEQ_NATIVE_FOUNDATION.out.logs.mix(CHIPSEQ_LEGACY_PEAKS.out.log)
        } else {
            completed_ch = CHIPSEQ_NATIVE_FOUNDATION.out.completed
            logs_ch = CHIPSEQ_NATIVE_FOUNDATION.out.logs
        }
    } else if (run_mode == 'consensus') {
        no_dep = channel.value('none')
        CHIPSEQ_LEGACY_CONSENSUS(
            'chipseq', 'consensus', 'high_cpu', config_file, legacy_root,
            seed, no_dep, no_dep
        )
        completed_ch = CHIPSEQ_LEGACY_CONSENSUS.out.status
        logs_ch = CHIPSEQ_LEGACY_CONSENSUS.out.log
    } else if (run_mode == 'idr') {
        error 'No scientifically equivalent legacy IDR provider exists; enable the native foundation, peak calling, Peak QC, and Consensus/IDR context'
    } else if (run_mode == 'differential_binding') {
        no_dep = channel.value('none')
        CHIPSEQ_LEGACY_DIFFERENTIAL(
            'chipseq', 'differential', 'high_memory', config_file, legacy_root,
            seed, no_dep, no_dep
        )
        completed_ch = CHIPSEQ_LEGACY_DIFFERENTIAL.out.status
        logs_ch = CHIPSEQ_LEGACY_DIFFERENTIAL.out.log
    } else if (run_mode in ['peaks', 'peak_qc'] && !native_peak_calling) {
        no_dep = channel.value('none')
        CHIPSEQ_LEGACY_PEAKS(
            'chipseq', 'peaks', 'high_cpu', config_file, legacy_root,
            seed, no_dep, no_dep
        )
        completed_ch = CHIPSEQ_LEGACY_PEAKS.out.status
        logs_ch = CHIPSEQ_LEGACY_PEAKS.out.log
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
