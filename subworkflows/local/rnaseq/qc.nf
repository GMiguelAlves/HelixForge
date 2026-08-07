include { LEGACY_STEP as RNASEQ_DOWNLOAD_STEP } from '../../../modules/local/legacy_step/main'
include { LEGACY_STEP as RNASEQ_METADATA_STEP } from '../../../modules/local/legacy_step/main'
include { LEGACY_STEP as RNASEQ_QC_STEP }       from '../../../modules/local/legacy_step/main'
include { RNASEQ_QC_PLAN }                      from '../../../modules/local/rnaseq_qc_plan/main'
include { TRIM_GALORE }                         from '../../../modules/local/trim_galore/main'

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
    if (params.rnaseq_native_trim_galore) {
        RNASEQ_QC_PLAN(
            config_file,
            file("${projectDir}/bin/annotate_qc_plan.py", checkIfExists: true),
            legacy_root,
            RNASEQ_DOWNLOAD_STEP.out.status,
            RNASEQ_METADATA_STEP.out.status
        )

        trim_inputs = RNASEQ_QC_PLAN.out.plans
            .splitCsv(header: true)
            .map { row ->
                def safe_run = row.run_accession.replaceAll(/[^A-Za-z0-9_.-]/, '_')
                def trim_r1 = file(row.trimmed_run_r1)
                def trim_r2 = file(row.trimmed_run_r2)
                def meta = [
                    dataset        : row.dataset,
                    sample_id      : row.sample_id,
                    run_accession  : safe_run,
                    trim_quality   : row.trim_quality,
                    trim_length    : row.trim_length,
                    trimmed_r1     : trim_r1.toString(),
                    trimmed_r2     : trim_r2.toString(),
                    trimmed_dir    : trim_r1.parent.toString(),
                    trimmed_r1_name: trim_r1.name,
                    trimmed_r2_name: trim_r2.name
                ]
                tuple(
                    meta,
                    file(row.raw_r1, checkIfExists: true),
                    file(row.raw_r2, checkIfExists: true)
                )
            }

        TRIM_GALORE(trim_inputs)
        native_trim_complete = TRIM_GALORE.out.status.collect()

        RNASEQ_QC_STEP(
            'rnaseq', 'qc', 'high_cpu', config_file, legacy_root,
            native_trim_complete,
            RNASEQ_QC_PLAN.out.plans.collect(),
            no_dep
        )

        qc_logs = RNASEQ_DOWNLOAD_STEP.out.log
            .mix(RNASEQ_METADATA_STEP.out.log)
            .mix(RNASEQ_QC_PLAN.out.log)
            .mix(TRIM_GALORE.out.log)
            .mix(RNASEQ_QC_STEP.out.log)
    } else {
        RNASEQ_QC_STEP(
            'rnaseq', 'qc', 'high_cpu', config_file, legacy_root,
            RNASEQ_DOWNLOAD_STEP.out.status,
            RNASEQ_METADATA_STEP.out.status,
            no_dep
        )

        qc_logs = RNASEQ_DOWNLOAD_STEP.out.log
            .mix(RNASEQ_METADATA_STEP.out.log)
            .mix(RNASEQ_QC_STEP.out.log)
    }

    emit:
    status = RNASEQ_QC_STEP.out.status
    logs   = qc_logs
}
