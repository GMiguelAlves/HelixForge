include { RNASEQ_NATIVE_FOUNDATION }        from '../subworkflows/local/rnaseq/native_foundation'
include { RNASEQ_QC }                       from '../subworkflows/local/rnaseq/qc'
include { RNASEQ_ALIGNMENT_QUANTIFICATION } from '../subworkflows/local/rnaseq/alignment_quantification'
include { RNASEQ_DIFFERENTIAL_EXPRESSION }  from '../subworkflows/local/rnaseq/differential_expression'

workflow RNASEQ {
    take:
    seed

    main:
    config_file = file(params.rnaseq_config, checkIfExists: true)
    legacy_root = "${projectDir}/pipelines/rnaseq/legacy"
    run_mode = params.rnaseq_run_mode.toString().toLowerCase()
    if (!(run_mode in ['qc', 'alignment', 'quant', 'quantification', 'import', 'de', 'differential_expression', 'report', 'full'])) {
        error "Invalid rnaseq_run_mode '${params.rnaseq_run_mode}'. Use qc, alignment, quantification, import, de, report, or full."
    }

    RNASEQ_NATIVE_FOUNDATION(config_file, legacy_root, seed)
    RNASEQ_QC(RNASEQ_NATIVE_FOUNDATION.out.qc_plans)
    if (run_mode == 'qc') {
        completed_status = RNASEQ_QC.out.status
        analysis_logs = channel.empty()
        downstream_logs = channel.empty()
    } else {
        RNASEQ_ALIGNMENT_QUANTIFICATION(
            config_file,
            legacy_root,
            RNASEQ_NATIVE_FOUNDATION.out.reference_status,
            RNASEQ_QC.out.status,
            RNASEQ_QC.out.plans,
            RNASEQ_NATIVE_FOUNDATION.out.metadata,
            RNASEQ_NATIVE_FOUNDATION.out.annotation
        )
        analysis_logs = RNASEQ_ALIGNMENT_QUANTIFICATION.out.logs
        if (run_mode in ['alignment', 'quant', 'quantification', 'import']) {
            completed_status = RNASEQ_ALIGNMENT_QUANTIFICATION.out.status
            downstream_logs = channel.empty()
        } else {
            RNASEQ_DIFFERENTIAL_EXPRESSION(
                config_file,
                legacy_root,
                RNASEQ_ALIGNMENT_QUANTIFICATION.out.status,
                RNASEQ_ALIGNMENT_QUANTIFICATION.out.import_manifest,
                RNASEQ_ALIGNMENT_QUANTIFICATION.out.imported_counts,
                RNASEQ_ALIGNMENT_QUANTIFICATION.out.imported_abundance,
                RNASEQ_ALIGNMENT_QUANTIFICATION.out.imported_metadata,
                RNASEQ_NATIVE_FOUNDATION.out.annotation
            )
            completed_status = RNASEQ_DIFFERENTIAL_EXPRESSION.out.status
            downstream_logs = RNASEQ_DIFFERENTIAL_EXPRESSION.out.logs
        }
    }

    emit:
    completed = completed_status
    logs      = RNASEQ_NATIVE_FOUNDATION.out.logs
        .mix(RNASEQ_QC.out.logs)
        .mix(analysis_logs)
        .mix(downstream_logs)
}
