include { LEGACY_STEP as RNASEQ_DOWNLOAD_STEP } from '../../../modules/local/legacy_step/main'
include { LEGACY_STEP as RNASEQ_METADATA_STEP } from '../../../modules/local/legacy_step/main'
include { LEGACY_STEP as RNASEQ_QC_STEP }       from '../../../modules/local/legacy_step/main'
include { RNASEQ_QC_PLAN }                      from '../../../modules/local/rnaseq_qc_plan/main'
include { FASTQC as FASTQC_RAW }                from '../../../modules/local/fastqc/main'
include { TRIM_GALORE }                         from '../../../modules/local/trim_galore/main'
include { FASTQC as FASTQC_TRIMMED }            from '../../../modules/local/fastqc/main'
include { MERGE_FASTQ }                         from '../../../modules/local/merge_fastq/main'
include { FASTQC as FASTQC_MERGED }             from '../../../modules/local/fastqc/main'
include { MULTIQC }                             from '../../../modules/local/multiqc/main'

workflow RNASEQ_QC {
    take:
    config_file
    legacy_root
    seed

    main:
    no_dep = channel.value('none')
    requested_native_qc = params.rnaseq_native_qc instanceof Boolean \
        ? params.rnaseq_native_qc \
        : params.rnaseq_native_qc.toString().toBoolean()
    native_trim_enabled = params.rnaseq_native_trim_galore instanceof Boolean \
        ? params.rnaseq_native_trim_galore \
        : params.rnaseq_native_trim_galore.toString().toBoolean()
    native_qc_enabled = requested_native_qc && native_trim_enabled

    RNASEQ_DOWNLOAD_STEP(
        'rnaseq', 'download', 'medium', config_file, legacy_root,
        seed, no_dep, no_dep
    )
    RNASEQ_METADATA_STEP(
        'rnaseq', 'metadata', 'medium', config_file, legacy_root,
        seed, no_dep, no_dep
    )

    if (native_qc_enabled) {
        RNASEQ_QC_PLAN(
            config_file,
            file("${projectDir}/bin/annotate_qc_plan.py", checkIfExists: true),
            legacy_root,
            RNASEQ_DOWNLOAD_STEP.out.status,
            RNASEQ_METADATA_STEP.out.status
        )

        qc_rows = RNASEQ_QC_PLAN.out.plans
            .splitCsv(header: true)

        raw_fastqc_inputs = qc_rows.flatMap { row ->
            def project_scratch = file(row.trimmed_run_r1).parent.parent.toString()
            def target_dir = "${project_scratch}/fastqc_raw"
            def safe_dataset = row.dataset.replaceAll(/[^A-Za-z0-9_.-]/, '_')
            def safe_sample = row.sample_id.replaceAll(/[^A-Za-z0-9_.-]/, '_')
            def safe_run = row.run_accession.replaceAll(/[^A-Za-z0-9_.-]/, '_')
            [
                tuple(
                    [
                        id             : "${safe_dataset}.${safe_sample}.${safe_run}.raw.R1",
                        dataset        : row.dataset,
                        sample_id      : row.sample_id,
                        run_accession  : row.run_accession,
                        phase          : 'raw',
                        project_scratch: project_scratch,
                        target_dir     : target_dir
                    ],
                    file(row.raw_r1, checkIfExists: true)
                ),
                tuple(
                    [
                        id             : "${safe_dataset}.${safe_sample}.${safe_run}.raw.R2",
                        dataset        : row.dataset,
                        sample_id      : row.sample_id,
                        run_accession  : row.run_accession,
                        phase          : 'raw',
                        project_scratch: project_scratch,
                        target_dir     : target_dir
                    ],
                    file(row.raw_r2, checkIfExists: true)
                )
            ]
        }

        trim_inputs = qc_rows.map { row ->
            def safe_dataset = row.dataset.replaceAll(/[^A-Za-z0-9_.-]/, '_')
            def safe_sample = row.sample_id.replaceAll(/[^A-Za-z0-9_.-]/, '_')
            def safe_run = row.run_accession.replaceAll(/[^A-Za-z0-9_.-]/, '_')
            def trim_r1 = file(row.trimmed_run_r1)
            def trim_r2 = file(row.trimmed_run_r2)
            def merged_r1 = file(row.merged_sample_r1)
            def merged_r2 = file(row.merged_sample_r2)
            def meta = [
                id              : "${safe_dataset}.${safe_sample}.${safe_run}.trim_galore",
                dataset         : row.dataset,
                sample_id       : row.sample_id,
                run_accession   : row.run_accession,
                trim_quality    : row.trim_quality,
                trim_length     : row.trim_length,
                trimmed_r1      : trim_r1.toString(),
                trimmed_r2      : trim_r2.toString(),
                trimmed_dir     : trim_r1.parent.toString(),
                trimmed_r1_name : trim_r1.name,
                trimmed_r2_name : trim_r2.name,
                merged_r1       : merged_r1.toString(),
                merged_r2       : merged_r2.toString(),
                merged_r1_name  : merged_r1.name,
                merged_r2_name  : merged_r2.name,
                project_scratch : trim_r1.parent.parent.toString(),
                safe_dataset    : safe_dataset,
                safe_sample     : safe_sample,
                safe_run        : safe_run
            ]
            tuple(
                meta,
                file(row.raw_r1, checkIfExists: true),
                file(row.raw_r2, checkIfExists: true)
            )
        }

        FASTQC_RAW(raw_fastqc_inputs)
        TRIM_GALORE(trim_inputs)

        trimmed_fastqc_inputs = TRIM_GALORE.out.artifacts.flatMap { meta, trimmed_r1, trimmed_r2 ->
            def target_dir = "${meta.project_scratch}/fastqc_trimmed_runs"
            [
                tuple(meta + [id: "${meta.safe_dataset}.${meta.safe_sample}.${meta.safe_run}.trimmed.R1", phase: 'trimmed', target_dir: target_dir], trimmed_r1),
                tuple(meta + [id: "${meta.safe_dataset}.${meta.safe_sample}.${meta.safe_run}.trimmed.R2", phase: 'trimmed', target_dir: target_dir], trimmed_r2)
            ]
        }

        merge_inputs = TRIM_GALORE.out.artifacts
            .map { meta, trimmed_r1, trimmed_r2 ->
                tuple(meta.dataset, meta.sample_id, tuple(meta, trimmed_r1, trimmed_r2))
            }
            .groupTuple(by: [0, 1])
            .map { dataset, sample_id, run_records ->
                def ordered = run_records.sort { left, right ->
                    left[0].run_accession <=> right[0].run_accession
                }
                def first = ordered[0][0]
                def merge_meta = [
                    id             : "${first.safe_dataset}.${first.safe_sample}.merge",
                    dataset        : dataset,
                    sample_id      : sample_id,
                    safe_dataset   : first.safe_dataset,
                    safe_sample    : first.safe_sample,
                    project_scratch: first.project_scratch,
                    target_dir     : file(first.merged_r1).parent.toString(),
                    output_r1      : first.merged_r1,
                    output_r2      : first.merged_r2,
                    output_r1_name : first.merged_r1_name,
                    output_r2_name : first.merged_r2_name
                ]
                tuple(
                    merge_meta,
                    ordered.collect { record -> record[1] },
                    ordered.collect { record -> record[2] }
                )
            }

        FASTQC_TRIMMED(trimmed_fastqc_inputs)
        MERGE_FASTQ(merge_inputs)

        merged_fastqc_inputs = MERGE_FASTQ.out.artifacts.flatMap { meta, merged_r1, merged_r2 ->
            def target_dir = "${meta.project_scratch}/fastqc_merged"
            [
                tuple(meta + [id: "${meta.safe_dataset}.${meta.safe_sample}.merged.R1", phase: 'merged', target_dir: target_dir], merged_r1),
                tuple(meta + [id: "${meta.safe_dataset}.${meta.safe_sample}.merged.R2", phase: 'merged', target_dir: target_dir], merged_r2)
            ]
        }

        FASTQC_MERGED(merged_fastqc_inputs)

        multiqc_inputs = FASTQC_RAW.out.artifacts
            .mix(FASTQC_TRIMMED.out.artifacts)
            .mix(FASTQC_MERGED.out.artifacts)
            .map { meta, fastqc_zip ->
                tuple(meta.dataset, meta.project_scratch, fastqc_zip)
            }
            .groupTuple(by: [0, 1])
            .map { dataset, project_scratch, fastqc_zips ->
                def safe_dataset = dataset.replaceAll(/[^A-Za-z0-9_.-]/, '_')
                tuple(
                    [
                        id         : "${safe_dataset}.multiqc",
                        dataset    : dataset,
                        report_name: "${dataset}_multiqc_030.html",
                        target_dir : "${project_scratch}/multiqc_030"
                    ],
                    fastqc_zips
                )
            }

        MULTIQC(multiqc_inputs)

        qc_status = MULTIQC.out.status
        qc_logs = RNASEQ_DOWNLOAD_STEP.out.log
            .mix(RNASEQ_METADATA_STEP.out.log)
            .mix(RNASEQ_QC_PLAN.out.log)
            .mix(FASTQC_RAW.out.reports)
            .mix(TRIM_GALORE.out.reports)
            .mix(FASTQC_TRIMMED.out.reports)
            .mix(MERGE_FASTQ.out.reports)
            .mix(FASTQC_MERGED.out.reports)
            .mix(MULTIQC.out.reports)
    } else {
        RNASEQ_QC_STEP(
            'rnaseq', 'qc', 'high_cpu', config_file, legacy_root,
            RNASEQ_DOWNLOAD_STEP.out.status,
            RNASEQ_METADATA_STEP.out.status,
            no_dep
        )

        qc_status = RNASEQ_QC_STEP.out.status
        qc_logs = RNASEQ_DOWNLOAD_STEP.out.log
            .mix(RNASEQ_METADATA_STEP.out.log)
            .mix(RNASEQ_QC_STEP.out.log)
    }

    emit:
    status = qc_status
    logs   = qc_logs
}
