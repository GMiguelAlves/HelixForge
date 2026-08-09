include { CHIPSEQ_CONTEXT }  from '../../../modules/local/chipseq_context/main'
include { CHIPSEQ_METADATA } from '../../../modules/local/chipseq_metadata/main'
include { FASTQC }           from '../../../modules/local/fastqc/main'
include { MULTIQC }          from '../../../modules/local/multiqc/main'
include { REFERENCE_INDEX }  from '../../local/alignment/reference_index'
include { ALIGNMENT }        from '../../local/alignment/alignment'
include { CHIPSEQ_BAM_PROCESSING } from './bam_processing'

workflow CHIPSEQ_NATIVE_FOUNDATION {
    take:
    config_file
    legacy_root
    _seed

    main:
    mode = params.chipseq_run_mode.toString().toLowerCase()
    context_meta = channel.value([id: 'chipseq.context'])
    CHIPSEQ_CONTEXT(config_file, legacy_root, context_meta)
    CHIPSEQ_METADATA(CHIPSEQ_CONTEXT.out.artifacts)

    plan_rows = CHIPSEQ_METADATA.out.artifacts
        .map { _meta, plan -> plan }
        .splitCsv(header: true, sep: '\t')

    records = plan_rows.map { row ->
        def single_end = row.single_end.toBoolean()
        def reads = single_end \
            ? [file(row.fastq_1, checkIfExists: true)] \
            : [file(row.fastq_1, checkIfExists: true), file(row.fastq_2, checkIfExists: true)]
        def record_meta = [
            id                  : row.record_id,
            sample_id           : row.sample_id,
            run_accession       : row.run_accession,
            dataset             : row.dataset,
            condition           : row.condition,
            biological_replicate: row.biological_replicate,
            technical_replicate : row.technical_replicate,
            is_control          : row.is_control.toBoolean(),
            control_id          : row.control_id,
            target              : row.target,
            antibody            : row.antibody,
            genome_id           : row.genome_id,
            organism            : row.organism,
            single_end          : single_end,
            aligner             : 'bowtie2',
            qc_dir              : row.qc_dir,
            target_dir          : "${row.align_dir}/${row.record_id}",
            final_target_dir    : "${row.filter_dir}/${row.record_id}"
        ]
        def annotation = row.annotation_file \
            ? file(row.annotation_file, checkIfExists: true) \
            : []
        def configured_exclude_flags = row.remove_secondary_supplementary.toBoolean() ? 2308 : 4
        def selected_blacklist = params.chipseq_blacklist != null \
            ? params.chipseq_blacklist.toString() \
            : row.blacklist_bed
        def blacklist_path = selected_blacklist && !(selected_blacklist.toLowerCase() in ['none', 'false']) \
            ? file(selected_blacklist, checkIfExists: true) \
            : []
        def duplicate_mode = params.chipseq_duplicate_mode.toString().toLowerCase()
        if (duplicate_mode == 'legacy') {
            if (row.remove_duplicates.toBoolean() && row.dedup_tool.toLowerCase() != 'samtools') {
                error "Native duplicate compatibility currently supports samtools only; legacy DEDUP_TOOL is '${row.dedup_tool}'"
            }
            duplicate_mode = row.remove_duplicates.toBoolean() ? 'remove' : 'none'
        }
        tuple(
            record_meta,
            reads,
            row.genome_fasta,
            annotation,
            [
                extra_args    : row.bowtie2_opts,
                index_basename: file(row.index_prefix).name
            ],
            [
                blacklist: blacklist_path,
                select: [
                    min_mapq     : params.chipseq_min_mapq != null ? params.chipseq_min_mapq as Integer : row.min_mapq as Integer,
                    include_flags: params.chipseq_include_flags as Integer,
                    exclude_flags: params.chipseq_exclude_flags != null ? params.chipseq_exclude_flags as Integer : configured_exclude_flags,
                    region       : params.chipseq_region ?: ''
                ],
                duplicates: [mode: duplicate_mode],
                blacklist_params: [overlap_mode: params.chipseq_blacklist_overlap_mode.toString().toLowerCase()],
                final_qc: [sort_if_needed: params.chipseq_sort_final_if_needed as Boolean]
            ]
        )
    }

    qc_reads = records.flatMap { record_meta, record_reads, _reference, _annotation, _alignment_params, _bam_params ->
        record_reads.withIndex().collect { read, index ->
            def read_meta = record_meta + [
                id        : "${record_meta.id}.raw.R${index + 1}",
                target_dir: "${record_meta.qc_dir}/raw/${record_meta.id}"
            ]
            tuple(read_meta, read)
        }
    }
    FASTQC(qc_reads)

    qc_target = plan_rows
        .map { row -> row.qc_dir }
        .unique()
        .collect()
        .map { directories ->
            if (directories.size() != 1) {
                error "Native ChIP-seq records resolve to multiple QC directories: ${directories}"
            }
            directories[0]
        }
    multiqc_inputs = FASTQC.out.artifacts
        .map { _meta, zip -> zip }
        .collect()
        .combine(qc_target)
        .map { combined ->
            def values = combined as List
            def target = values[-1]
            def artifacts = values[0..-2]
            tuple(
                [
                    id         : 'chipseq.raw.multiqc',
                    report_name: 'raw_fastq_multiqc.html',
                    target_dir : "${target}/multiqc"
                ],
                artifacts
            )
        }
    MULTIQC(multiqc_inputs)

    alignment_status_ch = channel.empty()
    alignment_manifest_ch = channel.empty()
    alignment_reports_ch = channel.empty()
    bam_status_ch = channel.empty()
    bam_manifest_ch = channel.empty()
    bam_reports_ch = channel.empty()
    bam_artifacts_ch = channel.empty()
    if (mode in ['alignment', 'post_alignment']) {
        reference_inputs = plan_rows
            .map { row ->
                def prefix = file(row.index_prefix)
                def reference_meta = [
                    id        : "${row.genome_id}.bowtie2.index",
                    genome_id : row.genome_id,
                    organism  : row.organism,
                    aligner   : 'bowtie2',
                    target_dir: prefix.parent
                ]
                tuple(
                    reference_meta,
                    file(row.genome_fasta, checkIfExists: true),
                    [],
                    [
                        basename  : prefix.name,
                        extra_args: row.bowtie2_build_opts
                    ]
                )
            }
            .unique { index_meta, _reference, _annotation, index_params ->
                "${index_meta.genome_id}|${index_meta.target_dir}|${index_params.basename}|${index_params.extra_args}"
            }
        REFERENCE_INDEX(reference_inputs)

        alignment_inputs = records
            .combine(REFERENCE_INDEX.out.artifacts)
            .map { record_meta, record_reads, reference_text, annotation_path, alignment_params, _bam_params, _index_meta, index ->
                tuple(
                    record_meta,
                    record_reads,
                    file(reference_text, checkIfExists: true),
                    annotation_path,
                    index,
                    alignment_params
                )
            }
        ALIGNMENT(alignment_inputs)
        alignment_status_ch = ALIGNMENT.out.status
        alignment_manifest_ch = ALIGNMENT.out.manifest
        alignment_reports_ch = ALIGNMENT.out.reports

        if (mode == 'post_alignment') {
            if (!params.chipseq_native_bam_processing) {
                error 'chipseq_run_mode=post_alignment requires chipseq_native_bam_processing=true'
            }
            processing_context = records.map {
                record_meta, _record_reads, reference_text, _annotation_path, _alignment_params, bam_params ->
                tuple(record_meta.id, file(reference_text, checkIfExists: true), bam_params)
            }
            processing_inputs = ALIGNMENT.out.artifacts
                .map { record_meta, bam, bai -> tuple(record_meta.id, record_meta, bam, bai) }
                .join(processing_context)
                .map { _id, record_meta, bam, bai, reference, bam_params ->
                    tuple(
                        record_meta,
                        bam,
                        bai,
                        reference,
                        bam_params.blacklist,
                        bam_params.select,
                        bam_params.duplicates,
                        bam_params.blacklist_params,
                        bam_params.final_qc
                    )
                }
            CHIPSEQ_BAM_PROCESSING(processing_inputs)
            bam_status_ch = CHIPSEQ_BAM_PROCESSING.out.status
            bam_manifest_ch = CHIPSEQ_BAM_PROCESSING.out.final_manifest
            bam_reports_ch = CHIPSEQ_BAM_PROCESSING.out.reports
            bam_artifacts_ch = CHIPSEQ_BAM_PROCESSING.out.artifacts
        }
    }

    completed_ch = mode == 'qc' \
        ? MULTIQC.out.status \
        : (mode == 'post_alignment' ? bam_status_ch : alignment_status_ch)

    emit:
    completed           = completed_ch
    metadata            = CHIPSEQ_METADATA.out.reports
    qc_reports          = FASTQC.out.reports.mix(MULTIQC.out.reports)
    alignment_reports   = alignment_reports_ch
    alignment_manifests = alignment_manifest_ch
    final_bams          = bam_artifacts_ch
    final_bam_manifests = bam_manifest_ch
    bam_reports         = bam_reports_ch
    logs                = CHIPSEQ_CONTEXT.out.reports
        .mix(CHIPSEQ_METADATA.out.reports.map { metadata_meta, _normalized, _controls, _report, log -> tuple(metadata_meta, log) })
        .mix(FASTQC.out.reports.map { fastqc_meta, _html, log -> tuple(fastqc_meta, log) })
        .mix(MULTIQC.out.reports.map { multiqc_meta, _html, log -> tuple(multiqc_meta, log) })
}
