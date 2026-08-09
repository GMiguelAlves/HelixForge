include { CHIPSEQ_CONTEXT }  from '../../../modules/local/chipseq_context/main'
include { CHIPSEQ_METADATA } from '../../../modules/local/chipseq_metadata/main'
include { FASTQC }           from '../../../modules/local/fastqc/main'
include { MULTIQC }          from '../../../modules/local/multiqc/main'
include { REFERENCE_INDEX }  from '../../local/alignment/reference_index'
include { ALIGNMENT }        from '../../local/alignment/alignment'
include { CHIPSEQ_BAM_PROCESSING } from './bam_processing'
include { PEAK_CALLING_CONTEXT } from '../../../modules/local/peak_calling_context/main'
include { PEAK_CALLING } from './peak_calling'
include { PEAK_QC } from './peak_qc'
include { CONSENSUS_IDR } from './consensus'

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

    peak_context_artifacts_ch = channel.empty()
    if (mode in ['peaks', 'peak_qc', 'consensus', 'idr']) {
        def peak_spec = [
            caller                : params.chipseq_peak_caller,
            caller_version        : '3.0.4',
            peak_type             : params.chipseq_peak_type,
            effective_genome_size : params.chipseq_effective_genome_size,
            q_value               : params.chipseq_peak_q_value,
            p_value               : params.chipseq_peak_p_value,
            format                : params.chipseq_peak_format,
            duplicate_policy      : params.chipseq_peak_duplicate_policy,
            additional_args       : params.chipseq_peak_additional_args,
            output_dir            : params.chipseq_peak_output_dir,
        ]
        def peak_spec_base64 = groovy.json.JsonOutput.toJson(peak_spec).getBytes('UTF-8').encodeBase64().toString()
        peak_context_inputs = CHIPSEQ_METADATA.out.artifacts.map { meta, plan -> tuple(meta, plan, peak_spec_base64) }
        PEAK_CALLING_CONTEXT(peak_context_inputs)
        peak_context_artifacts_ch = PEAK_CALLING_CONTEXT.out.artifacts
        active_plan = PEAK_CALLING_CONTEXT.out.artifacts.map { _meta, validated_plan, _peak_plan -> validated_plan }
    } else {
        active_plan = CHIPSEQ_METADATA.out.artifacts.map { _meta, plan -> plan }
    }

    plan_rows = active_plan
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
        record_meta = record_meta + [
            bam_duplicate_policy: duplicate_mode,
            bam_min_mapq         : params.chipseq_min_mapq != null ? params.chipseq_min_mapq as Integer : row.min_mapq as Integer,
            bam_include_flags    : params.chipseq_include_flags as Integer,
            bam_exclude_flags    : params.chipseq_exclude_flags != null ? params.chipseq_exclude_flags as Integer : configured_exclude_flags,
            bam_blacklist_policy : params.chipseq_blacklist_overlap_mode.toString().toLowerCase(),
        ]
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
    peak_status_ch = channel.empty()
    peak_artifacts_ch = channel.empty()
    peak_manifests_ch = channel.empty()
    peak_reports_ch = channel.empty()
    peak_qc_status_ch = channel.empty()
    peak_qc_artifacts_ch = channel.empty()
    peak_qc_manifest_ch = channel.empty()
    peak_qc_replicate_manifests_ch = channel.empty()
    peak_qc_reports_ch = channel.empty()
    consolidation_status_ch = channel.empty()
    consolidation_artifacts_ch = channel.empty()
    consolidation_manifest_ch = channel.empty()
    consolidation_reports_ch = channel.empty()
    if (mode in ['alignment', 'post_alignment', 'peaks', 'peak_qc', 'consensus', 'idr']) {
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

        if (mode in ['post_alignment', 'peaks', 'peak_qc', 'consensus', 'idr']) {
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

            if (mode in ['peaks', 'peak_qc', 'consensus', 'idr']) {
                if (!params.chipseq_native_peak_calling.toString().toBoolean()) {
                    error "chipseq_run_mode=${mode} requires chipseq_native_peak_calling=true in the native path"
                }
                PEAK_CALLING(
                    CHIPSEQ_BAM_PROCESSING.out.artifacts,
                    CHIPSEQ_BAM_PROCESSING.out.final_manifest,
                    peak_context_artifacts_ch
                )
                peak_status_ch = PEAK_CALLING.out.status
                peak_artifacts_ch = PEAK_CALLING.out.artifacts
                peak_manifests_ch = PEAK_CALLING.out.manifests
                peak_reports_ch = PEAK_CALLING.out.reports

                if (mode in ['peak_qc', 'consensus', 'idr'] && params.chipseq_native_peak_qc.toString().toBoolean()) {
                    def peak_qc_spec = [
                        unit                     : params.chipseq_frip_unit,
                        min_mapq                 : params.chipseq_frip_min_mapq,
                        include_flags            : params.chipseq_frip_include_flags,
                        additional_exclude_flags : params.chipseq_frip_additional_exclude_flags,
                        exclude_unmapped         : params.chipseq_frip_exclude_unmapped,
                        exclude_secondary        : params.chipseq_frip_exclude_secondary,
                        exclude_supplementary    : params.chipseq_frip_exclude_supplementary,
                        exclude_qc_fail          : params.chipseq_frip_exclude_qc_fail,
                        duplicate_handling       : params.chipseq_frip_duplicate_handling,
                        require_proper_pair      : params.chipseq_frip_require_proper_pair,
                        overlap_strategy         : params.chipseq_frip_overlap_strategy,
                        blacklist_policy         : params.chipseq_frip_blacklist_policy,
                    ]
                    def peak_qc_spec_base64 = groovy.json.JsonOutput.toJson(peak_qc_spec).getBytes('UTF-8').encodeBase64().toString()
                    PEAK_QC(
                        CHIPSEQ_BAM_PROCESSING.out.artifacts,
                        CHIPSEQ_BAM_PROCESSING.out.final_manifest,
                        PEAK_CALLING.out.artifacts,
                        PEAK_CALLING.out.manifests,
                        peak_context_artifacts_ch,
                        channel.value(peak_qc_spec_base64)
                    )
                    peak_qc_status_ch = PEAK_QC.out.status
                    peak_qc_artifacts_ch = PEAK_QC.out.summary
                    peak_qc_manifest_ch = PEAK_QC.out.manifest
                    peak_qc_replicate_manifests_ch = PEAK_QC.out.replicate_manifests
                    peak_qc_reports_ch = PEAK_QC.out.reports

                    if (mode in ['consensus', 'idr']) {
                        if (!params.chipseq_native_consensus.toString().toBoolean()) {
                            error "chipseq_run_mode=${mode} requires chipseq_native_consensus=true in the native path"
                        }
                        def strategy = mode == 'idr' ? 'idr' : params.chipseq_consensus_method?.toString()?.toLowerCase()
                        if (!(strategy in ['union', 'intersection', 'replicate_support', 'idr'])) {
                            error 'Consensus mode requires explicit --chipseq_consensus_method union|intersection|replicate_support'
                        }
                        def consensus_spec = [
                            strategy            : strategy,
                            min_replicates       : params.chipseq_min_replicates,
                            replicate_mode       : params.chipseq_replicate_mode,
                            replicate_policy     : params.chipseq_replicate_policy,
                            require_same_caller  : params.chipseq_consensus_require_same_caller,
                            idr_threshold        : params.chipseq_idr_threshold,
                            rank_metric          : params.chipseq_idr_rank_metric,
                            nextflow_version      : workflow.nextflow.version,
                            pipeline_commit       : workflow.commitId ?: null,
                        ]
                        def consensus_spec_base64 = groovy.json.JsonOutput.toJson(consensus_spec).getBytes('UTF-8').encodeBase64().toString()
                        CONSENSUS_IDR(
                            PEAK_CALLING.out.artifacts,
                            PEAK_CALLING.out.manifests,
                            PEAK_QC.out.replicate_manifests,
                            peak_context_artifacts_ch,
                            channel.value(consensus_spec_base64)
                        )
                        consolidation_status_ch = CONSENSUS_IDR.out.status
                        consolidation_artifacts_ch = CONSENSUS_IDR.out.summary
                        consolidation_manifest_ch = CONSENSUS_IDR.out.manifest
                        consolidation_reports_ch = CONSENSUS_IDR.out.reports
                    }
                }
            }
        }
    }

    completed_ch = mode == 'qc' \
        ? MULTIQC.out.status \
        : (mode in ['consensus', 'idr'] \
            ? consolidation_status_ch \
            : (mode == 'peak_qc' \
            ? (params.chipseq_native_peak_qc.toString().toBoolean() ? peak_qc_status_ch : peak_status_ch) \
            : (mode == 'peaks' ? peak_status_ch : (mode == 'post_alignment' ? bam_status_ch : alignment_status_ch))))

    emit:
    completed           = completed_ch
    metadata            = CHIPSEQ_METADATA.out.reports
    qc_reports          = FASTQC.out.reports.mix(MULTIQC.out.reports)
    alignment_reports   = alignment_reports_ch
    alignment_manifests = alignment_manifest_ch
    final_bams          = bam_artifacts_ch
    final_bam_manifests = bam_manifest_ch
    bam_reports         = bam_reports_ch
    peaks               = peak_artifacts_ch
    peak_manifests      = peak_manifests_ch
    peak_reports        = peak_reports_ch
    peak_qc             = peak_qc_artifacts_ch
    peak_qc_manifest    = peak_qc_manifest_ch
    peak_qc_replicate_manifests = peak_qc_replicate_manifests_ch
    peak_qc_reports     = peak_qc_reports_ch
    consolidated_peaks  = consolidation_artifacts_ch
    consolidation_manifest = consolidation_manifest_ch
    consolidation_reports = consolidation_reports_ch
    logs                = CHIPSEQ_CONTEXT.out.reports
        .mix(CHIPSEQ_METADATA.out.reports.map { metadata_meta, _normalized, _controls, _report, log -> tuple(metadata_meta, log) })
        .mix(FASTQC.out.reports.map { fastqc_meta, _html, log -> tuple(fastqc_meta, log) })
        .mix(MULTIQC.out.reports.map { multiqc_meta, _html, log -> tuple(multiqc_meta, log) })
}
