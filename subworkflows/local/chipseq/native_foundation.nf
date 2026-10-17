include { CHIPSEQ_CONTEXT }  from '../../../modules/local/chipseq_context/main'
include { CHIPSEQ_METADATA } from '../../../modules/local/chipseq_metadata/main'
include { CHIPSEQ_EXECUTION_PLAN } from '../../../modules/local/chipseq_execution_plan/main'
include { FASTQC }           from '../../../modules/local/fastqc/main'
include { FASTQC as FASTQC_TRIMMED } from '../../../modules/local/fastqc/main'
include { READ_TRIMMING } from '../../local/qc/read_trimming'
include { MULTIQC }          from '../../../modules/local/multiqc/main'
include { REFERENCE_INDEX }  from '../../local/alignment/reference_index'
include { ALIGNMENT }        from '../../local/alignment/alignment'
include { CHIPSEQ_BAM_PROCESSING } from './bam_processing'
include { PEAK_CALLING_CONTEXT } from '../../../modules/local/peak_calling_context/main'
include { PEAK_CALLING } from './peak_calling'
include { PEAK_QC } from './peak_qc'
include { CONSENSUS_IDR } from './consensus'
include { DIFFERENTIAL_BINDING } from './differential_binding'
include { CHIPSEQ_REFERENCE_BUNDLE } from '../../../modules/local/chipseq_reference_bundle/main'
include { PEAK_ANNOTATION } from './peak_annotation'
include { TRACK_GENERATION } from './tracks'
include { CHIPSEQ_REPORT } from './report'
include { CHIPSEQ_FULL_REPORT_INPUT } from '../../../modules/local/chipseq_full_report_input/main'
include { RUN_MANIFEST } from '../../../modules/local/run_manifest/main'

workflow CHIPSEQ_NATIVE_FOUNDATION {
    take:
    config_file
    pipeline_root
    _seed

    main:
    mode = params.chipseq_run_mode.toString().toLowerCase()
    def db_flag = params.chipseq_db_enabled
    if (db_flag != null && !(db_flag.toString().toLowerCase() in ['true', 'false'])) {
        error '--chipseq_db_enabled must be true or false'
    }
    db_enabled = db_flag == null ? (mode == 'differential_binding' || (mode == 'full' && params.chipseq_db_spec != null)) : db_flag.toString().toBoolean()
    if (!(params.chipseq_postprocess.toString().toLowerCase() in ['true', 'false'])) { error '--chipseq_postprocess must be true or false' }
    if (params.chipseq_postprocess.toString().toBoolean() && !(mode in ['consensus', 'idr', 'full'])) { error '--chipseq_postprocess requires consensus, idr or full mode' }
    complete_outputs = mode == 'full' || (mode in ['consensus', 'idr'] && params.chipseq_postprocess.toString().toBoolean())
    if (db_enabled && !(mode in ['full', 'differential_binding'])) { error 'DB requires full or differential_binding mode' }
    if (mode == 'differential_binding' && !db_enabled) { error 'differential_binding mode cannot disable DB' }
    if (db_enabled && !params.chipseq_db_spec) { error 'Requested DB requires --chipseq_db_spec' }
    db_spec_file = db_enabled ? file(params.chipseq_db_spec, checkIfExists: true) : []
    trim_enabled = params.chipseq_trim.toString().toBoolean()
    if (trim_enabled && (params.chipseq_trim_quality == null || params.chipseq_trim_length == null)) {
        error '--chipseq_trim requires explicit --chipseq_trim_quality and --chipseq_trim_length'
    }
    has_prebuilt_index = params.chipseq_bowtie2_prebuilt_index != null && params.chipseq_bowtie2_prebuilt_index.toString().trim()
    has_prebuilt_manifest = params.chipseq_bowtie2_prebuilt_index_manifest != null && params.chipseq_bowtie2_prebuilt_index_manifest.toString().trim()
    if (has_prebuilt_index != has_prebuilt_manifest) {
        error '--chipseq_bowtie2_prebuilt_index and --chipseq_bowtie2_prebuilt_index_manifest must be supplied together'
    }
    context_meta = channel.value([id: 'chipseq.context'])
    CHIPSEQ_CONTEXT(config_file, pipeline_root, context_meta)
    CHIPSEQ_METADATA(CHIPSEQ_CONTEXT.out.artifacts)
    plan_inputs = CHIPSEQ_METADATA.out.artifacts.map { meta, plan ->
        tuple(meta, plan, db_spec_file, [mode: mode, differential_binding: db_enabled, postprocess: complete_outputs])
    }
    CHIPSEQ_EXECUTION_PLAN(plan_inputs)

    peak_context_artifacts_ch = channel.empty()
    if (mode in ['peaks', 'peak_qc', 'consensus', 'idr', 'differential_binding', 'full']) {
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
        peak_context_inputs = CHIPSEQ_EXECUTION_PLAN.out.artifacts.map { meta, plan, _execution_plan -> tuple(meta, plan, peak_spec_base64) }
        PEAK_CALLING_CONTEXT(peak_context_inputs)
        peak_context_artifacts_ch = PEAK_CALLING_CONTEXT.out.artifacts
        active_plan = PEAK_CALLING_CONTEXT.out.artifacts.map { _meta, validated_plan, _peak_plan -> validated_plan }
    } else {
        active_plan = CHIPSEQ_EXECUTION_PLAN.out.artifacts.map { _meta, plan, _execution_plan -> plan }
    }

    plan_rows = active_plan
        .splitCsv(header: true, sep: '\t')

    reference_bundle_artifacts_ch = channel.empty()
    reference_bundle_reports_ch = channel.empty()
    if (complete_outputs) {
        reference_bundle_inputs = plan_rows
            .map { row ->
                if (!row.annotation_file) {
                    error 'chipseq_run_mode=full requires an annotation file for every reference.'
                }
                def selected_blacklist = params.chipseq_blacklist != null \
                    ? params.chipseq_blacklist.toString() \
                    : row.blacklist_bed
                def blacklist_path = selected_blacklist && !(selected_blacklist.toLowerCase() in ['none', 'false']) \
                    ? file(selected_blacklist, checkIfExists: true) \
                    : []
                def reference_meta = [
                    id       : "${row.genome_id}.reference",
                    genome_id: row.genome_id,
                    build    : row.genome_id,
                    organism : row.organism,
                ]
                tuple(
                    reference_meta,
                    file(row.genome_fasta, checkIfExists: true),
                    file(row.annotation_file, checkIfExists: true),
                    blacklist_path
                )
            }
            .unique { meta, reference, annotation, blacklist ->
                "${meta.genome_id}|${reference}|${annotation}|${blacklist}"
            }
        CHIPSEQ_REFERENCE_BUNDLE(reference_bundle_inputs)
        reference_bundle_artifacts_ch = CHIPSEQ_REFERENCE_BUNDLE.out.artifacts
        reference_bundle_reports_ch = CHIPSEQ_REFERENCE_BUNDLE.out.reports
    }

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
                index_basename: file(row.index_prefix).name,
                index_key     : "${row.genome_id}|${file(row.index_prefix).parent}|${file(row.index_prefix).name}"
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

    selected_records = records
    trimming_manifests_ch = channel.empty()
    trimming_reports_ch = channel.empty()
    trimming_logs_ch = channel.empty()
    post_qc_artifacts_ch = channel.empty()
    post_qc_reports_ch = channel.empty()
    if (trim_enabled) {
        def trim_policy = [quality: params.chipseq_trim_quality, minimum_length: params.chipseq_trim_length,
            adapter: params.chipseq_trim_adapter, adapter2: params.chipseq_trim_adapter2]
        READ_TRIMMING(records.map { meta, reads, _reference, _annotation, _alignment, _bam -> tuple(meta, reads, trim_policy) })
        selected_records = records
            .map { meta, _reads, reference, annotation, alignment, bam -> tuple(meta.id, reference, annotation, alignment, bam) }
            .join(READ_TRIMMING.out.artifacts.map { meta, reads -> tuple(meta.id, meta, reads) })
            .map { _id, reference, annotation, alignment, bam, meta, reads -> tuple(meta, reads, reference, annotation, alignment, bam) }
        trimming_manifests_ch = READ_TRIMMING.out.manifest
        trimming_reports_ch = READ_TRIMMING.out.reports
        trimming_logs_ch = READ_TRIMMING.out.logs
        post_qc_inputs = READ_TRIMMING.out.artifacts.flatMap { meta, reads ->
            reads.withIndex().collect { read, index ->
                tuple(meta + [id: "${meta.id}.trimmed.R${index + 1}",
                    target_dir: "${meta.qc_dir}/trimmed/${meta.id}"], read)
            }
        }
        FASTQC_TRIMMED(post_qc_inputs)
        post_qc_artifacts_ch = FASTQC_TRIMMED.out.artifacts
        post_qc_reports_ch = FASTQC_TRIMMED.out.reports
    }

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
        .mix(post_qc_artifacts_ch)
        .map { _meta, zip -> zip }
        .mix(trimming_reports_ch.map { _meta, directory -> directory })
        .collect()
        .combine(qc_target)
        .map { combined ->
            def values = combined as List
            def target = values[-1]
            def artifacts = values[0..-2]
            tuple(
                [
                    id         : trim_enabled ? 'chipseq.trimmed.multiqc' : 'chipseq.raw.multiqc',
                    report_name: trim_enabled ? 'trimmed_fastq_multiqc.html' : 'raw_fastq_multiqc.html',
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
    differential_binding_status_ch = channel.empty()
    differential_binding_artifacts_ch = channel.empty()
    differential_binding_manifest_ch = channel.empty()
    differential_binding_reports_ch = channel.empty()
    db_contrast_manifest_ch = channel.empty()
    db_results_ch = channel.empty()
    db_contrast_results_ch = channel.empty()
    full_status_ch = channel.empty()
    full_reports_ch = channel.empty()
    full_annotation_artifacts_ch = channel.empty()
    full_annotation_manifest_ch = channel.empty()
    full_track_artifacts_ch = channel.empty()
    full_track_manifest_ch = channel.empty()
    full_report_artifacts_ch = channel.empty()
    terminal_manifest_ch = channel.empty()
    terminal_bundle_ch = channel.empty()
    if (mode in ['alignment', 'post_alignment', 'peaks', 'peak_qc', 'consensus', 'idr', 'differential_binding', 'full']) {
        reference_inputs = plan_rows
            .map { row ->
                def prefix = file(row.index_prefix)
                def reference_meta = [
                    id        : "${row.genome_id}.bowtie2.index",
                    genome_id : row.genome_id,
                    organism  : row.organism,
                    aligner   : 'bowtie2',
                    index_key : "${row.genome_id}|${prefix.parent}|${prefix.name}",
                    target_dir: prefix.parent
                ]
                def index_params = [basename: prefix.name, extra_args: row.bowtie2_build_opts]
                if (has_prebuilt_index) {
                    index_params = index_params + [
                        prebuilt_index: file(params.chipseq_bowtie2_prebuilt_index, checkIfExists: true),
                        prebuilt_manifest: file(params.chipseq_bowtie2_prebuilt_index_manifest, checkIfExists: true)
                    ]
                }
                tuple(
                    reference_meta,
                    file(row.genome_fasta, checkIfExists: true),
                    [],
                    index_params
                )
            }
            .unique { index_meta, _reference, _annotation, index_params ->
                "${index_meta.genome_id}|${index_meta.target_dir}|${index_params.basename}|${index_params.extra_args}"
            }
        REFERENCE_INDEX(reference_inputs)

        records_by_index = selected_records.map {
            record_meta, record_reads, reference_text, annotation_path, alignment_params, bam_params ->
            tuple(alignment_params.index_key, record_meta, record_reads, reference_text, annotation_path, alignment_params, bam_params)
        }
        indexes_by_key = REFERENCE_INDEX.out.artifacts.map { index_meta, index ->
            tuple(index_meta.index_key, index)
        }
        alignment_inputs = records_by_index
            .combine(indexes_by_key, by: 0)
            .map { _index_key, record_meta, record_reads, reference_text, annotation_path, alignment_params, _bam_params, index ->
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

        if (mode in ['post_alignment', 'peaks', 'peak_qc', 'consensus', 'idr', 'differential_binding', 'full']) {
            processing_context = records.map {
                record_meta, _record_reads, reference_text, _annotation_path, _alignment_params, bam_params ->
                tuple(record_meta.id, file(reference_text, checkIfExists: true), bam_params)
            }
            processing_inputs = ALIGNMENT.out.artifacts
                .map { record_meta, bam, bai -> tuple(record_meta.id, record_meta, bam, bai) }
                .join(ALIGNMENT.out.manifest.map { record_meta, manifest -> tuple(record_meta.id, manifest) })
                .join(processing_context)
                .map { _id, record_meta, bam, bai, alignment_manifest, reference, bam_params ->
                    tuple(
                        record_meta,
                        bam,
                        bai,
                        reference,
                        bam_params.blacklist,
                        bam_params.select,
                        bam_params.duplicates,
                        bam_params.blacklist_params,
                        bam_params.final_qc,
                        alignment_manifest
                    )
                }
            CHIPSEQ_BAM_PROCESSING(processing_inputs)
            bam_status_ch = CHIPSEQ_BAM_PROCESSING.out.status
            bam_manifest_ch = CHIPSEQ_BAM_PROCESSING.out.final_manifest
            bam_reports_ch = CHIPSEQ_BAM_PROCESSING.out.reports
            bam_artifacts_ch = CHIPSEQ_BAM_PROCESSING.out.artifacts

            if (mode in ['peaks', 'peak_qc', 'consensus', 'idr', 'differential_binding', 'full']) {
                PEAK_CALLING(
                    CHIPSEQ_BAM_PROCESSING.out.artifacts,
                    CHIPSEQ_BAM_PROCESSING.out.final_manifest,
                    peak_context_artifacts_ch
                )
                peak_status_ch = PEAK_CALLING.out.status
                peak_artifacts_ch = PEAK_CALLING.out.artifacts
                peak_manifests_ch = PEAK_CALLING.out.manifests
                peak_reports_ch = PEAK_CALLING.out.reports

                if (mode in ['peak_qc', 'consensus', 'idr', 'differential_binding', 'full']) {
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

                    if (mode in ['consensus', 'idr', 'differential_binding', 'full']) {
                        def strategy = mode == 'idr' ? 'idr' : params.chipseq_consensus_method?.toString()?.toLowerCase()
                        if (!(strategy in ['union', 'intersection', 'replicate_support', 'idr'])) {
                            error 'Consensus mode requires explicit --chipseq_consensus_method union|intersection|replicate_support|idr'
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

                        if (db_enabled) {
                            DIFFERENTIAL_BINDING(
                                CONSENSUS_IDR.out.artifacts,
                                CONSENSUS_IDR.out.provider_manifests,
                                CHIPSEQ_BAM_PROCESSING.out.artifacts,
                                CHIPSEQ_BAM_PROCESSING.out.final_manifest,
                                peak_context_artifacts_ch,
                                channel.value(db_spec_file)
                            )
                            differential_binding_status_ch = DIFFERENTIAL_BINDING.out.status
                            differential_binding_artifacts_ch = DIFFERENTIAL_BINDING.out.artifacts
                            differential_binding_manifest_ch = DIFFERENTIAL_BINDING.out.manifest
                            differential_binding_reports_ch = DIFFERENTIAL_BINDING.out.reports
                            db_contrast_manifest_ch = DIFFERENTIAL_BINDING.out.contrast_manifest
                            db_results_ch = DIFFERENTIAL_BINDING.out.results
                            db_contrast_results_ch = DIFFERENTIAL_BINDING.out.contrast_results
                        }

                            if (complete_outputs) {
                                full_project_meta_ch = plan_rows
                                    .map { row ->
                                        tuple(row.dataset, row.genome_id, row.organism)
                                    }
                                    .unique()
                                    .toList()
                                    .map { projects ->
                                        if (projects.size() != 1) {
                                            error "chipseq_run_mode=full currently requires one dataset/genome; observed ${projects}"
                                        }
                                        def project = projects[0]
                                        def report_id = "${project[0]}.chipseq_report".replaceAll(/[^A-Za-z0-9._-]+/, '_')
                                        [
                                            id        : report_id,
                                            project_id: project[0],
                                            dataset   : project[0],
                                            genome_id : project[1],
                                            build     : project[1],
                                            organism  : project[2],
                                            required_components: ['metadata', 'reference', 'alignment', 'bam', 'peak', 'peak_qc', 'consensus_idr', 'annotation', 'tracks'] + (db_enabled ? ['differential_binding'] : []),
                                        ]
                                    }

                                def annotation_spec = [
                                    provider            : params.chipseq_annotation_provider,
                                    mode                : params.chipseq_annotation_mode,
                                    overlap_mode        : params.chipseq_annotation_overlap_mode,
                                    promoter_upstream   : params.chipseq_annotation_promoter_upstream as Integer,
                                    promoter_downstream : params.chipseq_annotation_promoter_downstream as Integer,
                                    max_tss_distance    : params.chipseq_annotation_max_tss_distance,
                                    feature_priority    : params.chipseq_annotation_feature_priority.toString().split(',').collect { value -> value.trim() },
                                    gene_assignment     : params.chipseq_annotation_gene_assignment,
                                    strand_aware        : params.chipseq_annotation_strand_aware.toString().toBoolean(),
                                    intergenic_policy   : params.chipseq_annotation_intergenic_policy,
                                ]
                                def annotation_spec_base64 = groovy.json.JsonOutput.toJson(annotation_spec).getBytes('UTF-8').encodeBase64().toString()
                                annotation_references = reference_bundle_artifacts_ch.map { reference_meta, reference, annotation, manifest ->
                                    tuple(reference_meta.genome_id, reference, annotation, manifest)
                                }
                                annotation_sources = CONSENSUS_IDR.out.artifacts
                                    .map { consensus_meta, directory -> tuple(consensus_meta.id, consensus_meta, directory) }
                                    .join(CONSENSUS_IDR.out.provider_manifests.map { consensus_meta, manifest -> tuple(consensus_meta.id, manifest) })
                                    .map { _id, consensus_meta, directory, manifest ->
                                        tuple(consensus_meta.genome_id, consensus_meta, directory, manifest)
                                    }
                                annotation_inputs = annotation_sources
                                    .combine(annotation_references, by: 0)
                                    .map { _genome_id, consensus_meta, directory, consensus_manifest, reference, annotation, reference_manifest ->
                                        def annotation_meta = consensus_meta + [
                                            id       : "${consensus_meta.id}.annotation".replaceAll(/[^A-Za-z0-9._-]+/, '_'),
                                            source_id: consensus_meta.id,
                                        ]
                                        tuple(
                                            annotation_meta,
                                            file("${directory}/consolidated_peaks.bed", checkIfExists: true),
                                            consensus_manifest,
                                            reference,
                                            reference_manifest,
                                            annotation,
                                            annotation_spec_base64
                                        )
                                    }
                                PEAK_ANNOTATION(annotation_inputs)
                                full_annotation_artifacts_ch = PEAK_ANNOTATION.out.artifacts
                                full_annotation_manifest_ch = PEAK_ANNOTATION.out.manifest

                                def track_spec = [
                                    provider             : params.chipseq_track_provider,
                                    track_format         : params.chipseq_track_format,
                                    bin_size             : params.chipseq_track_bin_size as Integer,
                                    normalization        : params.chipseq_track_normalization,
                                    effective_genome_size: params.chipseq_track_effective_genome_size != null ? params.chipseq_track_effective_genome_size as Integer : null,
                                    scale_factor         : params.chipseq_track_scale_factor as Double,
                                    extend_reads         : params.chipseq_track_extend_reads.toString().toBoolean(),
                                    fragment_mode        : params.chipseq_track_fragment_mode,
                                    strand               : params.chipseq_track_strand,
                                    additional_filters   : params.chipseq_track_additional_filters,
                                ]
                                def track_spec_base64 = groovy.json.JsonOutput.toJson(track_spec).getBytes('UTF-8').encodeBase64().toString()
                                track_references = reference_bundle_artifacts_ch.map { reference_meta, reference, _annotation, manifest ->
                                    tuple(reference_meta.genome_id, reference, manifest)
                                }
                                track_sources = CHIPSEQ_BAM_PROCESSING.out.artifacts
                                    .map { record_meta, bam, bai -> tuple(record_meta.id, record_meta, bam, bai) }
                                    .join(CHIPSEQ_BAM_PROCESSING.out.final_manifest.map { record_meta, manifest -> tuple(record_meta.id, manifest) })
                                    .map { _id, record_meta, bam, bai, manifest -> tuple(record_meta.genome_id, record_meta, bam, bai, manifest) }
                                    .combine(track_references, by: 0)
                                    .map { _genome_id, record_meta, bam, bai, manifest, reference, reference_manifest ->
                                        tuple(record_meta, bam, bai, manifest, reference, reference_manifest)
                                    }
                                individual_track_inputs = track_sources.map { record_meta, bam, bai, manifest, reference, reference_manifest ->
                                    def track_meta = [
                                        id                    : "${record_meta.id}.bigwig".replaceAll(/[^A-Za-z0-9._-]+/, '_'),
                                        track_role            : 'individual',
                                        record_id             : record_meta.id,
                                        record_ids            : [record_meta.id],
                                        sample_ids            : [record_meta.sample_id],
                                        dataset               : record_meta.dataset,
                                        condition             : record_meta.condition,
                                        target                : record_meta.target,
                                        is_control            : record_meta.is_control,
                                        biological_replicates : [record_meta.biological_replicate],
                                        technical_replicates  : [record_meta.technical_replicate],
                                        genome_id             : record_meta.genome_id,
                                        build                 : record_meta.genome_id,
                                    ]
                                    tuple(track_meta, [bam], [bai], [manifest], reference, reference_manifest, track_spec_base64)
                                }
                                aggregate_track_inputs = channel.empty()
                                if (params.chipseq_track_aggregate.toString().toBoolean()) {
                                    if (params.chipseq_track_aggregate_scope != 'condition_target') {
                                        error 'Native Track Generation v1 supports only chipseq_track_aggregate_scope=condition_target'
                                    }
                                    aggregate_track_inputs = track_sources
                                        .filter { record_meta, _bam, _bai, _manifest, _reference, _reference_manifest -> !record_meta.is_control }
                                        .map { record_meta, bam, bai, manifest, reference, reference_manifest ->
                                            def group_key = [record_meta.dataset, record_meta.condition, record_meta.target, record_meta.genome_id].join('\u001f')
                                            tuple(group_key, record_meta, bam, bai, manifest, reference, reference_manifest)
                                        }
                                        .groupTuple(by: 0)
                                        .map { _group_key, record_metas, bams, bais, manifests, references, reference_manifests ->
                                            def ordered = (0..<record_metas.size()).toList().sort { left, right -> record_metas[left].id <=> record_metas[right].id }
                                            def metas = ordered.collect { index -> record_metas[index] }
                                            def first = metas[0]
                                            if (references.collect { reference -> reference.toString() }.toSet().size() != 1 || reference_manifests.collect { manifest -> manifest.toString() }.toSet().size() != 1) {
                                                error "Aggregate track group ${first.dataset}/${first.condition}/${first.target} resolved to multiple references"
                                            }
                                            def group_id = ['aggregate', first.dataset, first.condition, first.target, first.genome_id, 'bigwig']
                                                .collect { value -> value.toString().replaceAll(/[^A-Za-z0-9._-]+/, '_') }.join('.')
                                            def track_meta = [
                                                id                    : group_id,
                                                track_role            : 'aggregate',
                                                record_id             : null,
                                                record_ids            : metas.collect { record -> record.id },
                                                sample_ids            : metas.collect { record -> record.sample_id },
                                                dataset               : first.dataset,
                                                condition             : first.condition,
                                                target                : first.target,
                                                is_control            : false,
                                                biological_replicates : metas.collect { record -> record.biological_replicate },
                                                technical_replicates  : metas.collect { record -> record.technical_replicate },
                                                genome_id             : first.genome_id,
                                                build                 : first.genome_id,
                                            ]
                                            tuple(
                                                track_meta,
                                                ordered.collect { index -> bams[index] },
                                                ordered.collect { index -> bais[index] },
                                                ordered.collect { index -> manifests[index] },
                                                references[0],
                                                reference_manifests[0],
                                                track_spec_base64
                                            )
                                        }
                                }
                                TRACK_GENERATION(individual_track_inputs.mix(aggregate_track_inputs))
                                full_track_artifacts_ch = TRACK_GENERATION.out.artifacts
                                full_track_manifest_ch = TRACK_GENERATION.out.manifest

                                full_manifest_files_ch = CHIPSEQ_METADATA.out.manifest.map { _meta, manifest -> manifest }
                                    .mix(trimming_manifests_ch.map { _meta, manifest -> manifest })
                                    .mix(reference_bundle_artifacts_ch.map { _meta, _reference, _annotation, manifest -> manifest })
                                    .mix(ALIGNMENT.out.manifest.map { _meta, manifest -> manifest })
                                    .mix(CHIPSEQ_BAM_PROCESSING.out.final_manifest.map { _meta, manifest -> manifest })
                                    .mix(PEAK_CALLING.out.manifests.map { _meta, manifest -> manifest })
                                    .mix(PEAK_QC.out.manifest.map { _meta, manifest -> manifest })
                                    .mix(CONSENSUS_IDR.out.manifest.map { _meta, manifest -> manifest })
                                    .mix(differential_binding_manifest_ch.map { _meta, manifest -> manifest })
                                    .mix(db_contrast_manifest_ch.map { _meta, manifest -> manifest })
                                    .mix(PEAK_ANNOTATION.out.manifest.map { _meta, manifest -> manifest })
                                    .mix(TRACK_GENERATION.out.manifest.map { _meta, manifest -> manifest })
                                full_semantic_artifacts_ch = PEAK_QC.out.summary.map { _meta, summary_json, _summary_tsv -> summary_json }
                                    .mix(CONSENSUS_IDR.out.summary.map { _meta, summary_json, _summary_tsv -> summary_json })
                                    .mix(differential_binding_artifacts_ch.map { _meta, directory -> file("${directory}/differential_binding_summary.tsv", checkIfExists: true) })
                                    .mix(PEAK_ANNOTATION.out.artifacts.map { _meta, directory -> file("${directory}/statistics.tsv", checkIfExists: true) })
                                    .mix(TRACK_GENERATION.out.artifacts.map { _meta, directory -> file("${directory}/tracks.tsv", checkIfExists: true) })
                                full_report_materials_ch = full_manifest_files_ch
                                    .collect()
                                    .map { paths -> tuple('full_report', paths.sort { left, right -> left.name <=> right.name }) }
                                    .join(full_semantic_artifacts_ch.collect().map { paths -> tuple('full_report', paths.sort { left, right -> left.name <=> right.name }) })
                                full_report_input_ch = full_project_meta_ch
                                    .map { meta -> tuple('full_report', meta) }
                                    .join(full_report_materials_ch)
                                    .map { _key, meta, manifests, artifacts -> tuple(meta, manifests, artifacts) }
                                CHIPSEQ_FULL_REPORT_INPUT(full_report_input_ch)

                                def presentation = [
                                    provider: params.chipseq_report_provider,
                                    title   : params.chipseq_report_title,
                                    language: params.chipseq_report_language,
                                ]
                                def presentation_base64 = groovy.json.JsonOutput.toJson(presentation).getBytes('UTF-8').encodeBase64().toString()
                                report_records = CHIPSEQ_FULL_REPORT_INPUT.out.artifacts
                                    .map { meta, inventory -> tuple('full_report', meta, inventory) }
                                    .join(full_report_materials_ch)
                                    .map { _key, meta, inventory, manifests, artifacts ->
                                        tuple(meta, inventory, manifests, artifacts, presentation_base64)
                                    }
                                CHIPSEQ_REPORT(report_records)
                                full_status_ch = CHIPSEQ_REPORT.out.status
                                full_report_artifacts_ch = CHIPSEQ_REPORT.out.artifacts
                                full_reports_ch = PEAK_ANNOTATION.out.reports
                                    .mix(TRACK_GENERATION.out.reports)
                                    .mix(CHIPSEQ_FULL_REPORT_INPUT.out.reports)
                                    .mix(CHIPSEQ_REPORT.out.reports)

                                full_marks_ch = plan_rows
                                    .filter { row -> !row.is_control.toBoolean() }
                                    .map { row -> row.target }
                                    .unique()
                                    .toList()
                                full_marks_bundle_ch = full_marks_ch.map { marks -> [values: marks] }
                                bam_terminal_records = CHIPSEQ_BAM_PROCESSING.out.artifacts.map { record_meta, bam, _bai ->
                                    tuple([
                                        artifact_id: "${record_meta.id}.final_bam", artifact_type: 'aligned_bam', assay: 'chipseq',
                                        format: 'bam', entity_level: 'sample', contrast_id: null, sample_ids: [record_meta.sample_id],
                                        condition: record_meta.condition, stage: null, mark_or_factor: record_meta.target,
                                        marks_or_factors: [], peak_type: null, role: 'final_bam',
                                        producer_manifest_id: record_meta.id, producer_process: 'BAM_INDEX_QC',
                                        location: [kind: 'producer_relative', path: bam.name, base_path: null, producer_manifest_id: record_meta.id],
                                        source: [type: 'helixforge', name: 'samtools', version: null],
                                        metadata: [record_id: record_meta.id, is_control: record_meta.is_control]
                                    ], bam)
                                }
                                peak_terminal_records = PEAK_CALLING.out.artifacts.map { peak_meta, directory ->
                                    def extension = peak_meta.peak_type == 'narrow' ? 'narrowPeak' : 'broadPeak'
                                    tuple([
                                        artifact_id: "${peak_meta.id}.peak_set", artifact_type: 'peak_set', assay: 'chipseq',
                                        format: extension, entity_level: 'peak', contrast_id: null, sample_ids: [peak_meta.sample_id],
                                        condition: peak_meta.condition, stage: null, mark_or_factor: peak_meta.target,
                                        marks_or_factors: [], peak_type: peak_meta.peak_type, role: 'replicate_peaks',
                                        producer_manifest_id: peak_meta.id, producer_process: 'PEAK_CALLING_AGGREGATE',
                                        location: [kind: 'producer_relative', path: "peaks.${extension}", base_path: null, producer_manifest_id: peak_meta.id],
                                        source: [type: 'helixforge', name: peak_meta.caller, version: peak_meta.caller_version], metadata: [record_id: peak_meta.record_id]
                                    ], file("${directory}/peaks.${extension}", checkIfExists: true))
                                }
                                peak_qc_terminal_records = PEAK_QC.out.summary
                                    .combine(full_marks_bundle_ch)
                                    .map { qc_meta, _summary_json, summary_tsv, mark_bundle ->
                                    def marks = mark_bundle.values
                                    tuple([
                                        artifact_id: "${qc_meta.id}.summary", artifact_type: 'peak_qc', assay: 'chipseq',
                                        format: 'tsv', entity_level: 'peak', contrast_id: null, sample_ids: [],
                                        condition: null, stage: null, mark_or_factor: null, marks_or_factors: marks,
                                        peak_type: null, role: 'quality_control', producer_manifest_id: qc_meta.id, producer_process: 'PEAK_QC_AGGREGATE',
                                        location: [kind: 'producer_relative', path: summary_tsv.name, base_path: null, producer_manifest_id: qc_meta.id],
                                        source: [type: 'helixforge', name: 'Peak QC API', version: '1.0'], metadata: [:]
                                    ], summary_tsv)
                                }
                                consensus_terminal_records = CONSENSUS_IDR.out.artifacts.map { consensus_meta, directory ->
                                    def artifact_type = strategy == 'idr' ? 'idr_peaks' : 'consensus_peaks'
                                    tuple([
                                        artifact_id: "${consensus_meta.id}.${artifact_type}", artifact_type: artifact_type, assay: 'chipseq',
                                        format: 'bed', entity_level: 'peak', contrast_id: null, sample_ids: [],
                                        condition: consensus_meta.condition, stage: null, mark_or_factor: consensus_meta.target,
                                        marks_or_factors: [], peak_type: consensus_meta.peak_type, role: 'consolidated_peaks',
                                        producer_manifest_id: consensus_meta.id, producer_process: strategy == 'idr' ? 'IDR_PROVIDER' : 'CONSENSUS_INTERVALS',
                                        location: [kind: 'producer_relative', path: 'consolidated_peaks.bed', base_path: null, producer_manifest_id: consensus_meta.id],
                                        source: [type: 'helixforge', name: strategy, version: '1.0'], metadata: [strategy: strategy]
                                    ], file("${directory}/consolidated_peaks.bed", checkIfExists: true))
                                }
                                db_terminal_records = db_results_ch
                                    .combine(full_marks_bundle_ch)
                                    .map { db_meta, results, mark_bundle ->
                                    def marks = mark_bundle.values
                                    tuple([
                                        artifact_id: "${db_meta.id}.results", artifact_type: 'differential_binding', assay: 'chipseq',
                                        format: 'tsv', entity_level: 'peak', contrast_id: null, sample_ids: [],
                                        condition: null, stage: null, mark_or_factor: null, marks_or_factors: marks,
                                        peak_type: null, role: 'results', producer_manifest_id: db_meta.id, producer_process: 'DB_AGGREGATE',
                                        location: [kind: 'producer_relative', path: results.name, base_path: null, producer_manifest_id: db_meta.id],
                                        source: [type: 'helixforge', name: 'DESeq2', version: null], metadata: [:]
                                    ], results)
                                }
                                db_contrast_terminal_records = db_contrast_results_ch
                                    .combine(full_marks_bundle_ch)
                                    .map { db_meta, results, mark_bundle ->
                                    def marks = mark_bundle.values
                                    tuple([
                                        artifact_id: "${db_meta.id}.differential_binding", artifact_type: 'differential_binding', assay: 'chipseq',
                                        format: 'tsv', entity_level: 'peak', contrast_id: db_meta.contrast_id, sample_ids: [],
                                        condition: null, stage: null, mark_or_factor: null, marks_or_factors: marks,
                                        peak_type: null, role: 'contrast_results', producer_manifest_id: db_meta.id, producer_process: 'DESEQ2_DB_CONTRAST',
                                        location: [kind: 'producer_relative', path: results.name, base_path: null, producer_manifest_id: db_meta.id],
                                        source: [type: 'helixforge', name: 'DESeq2', version: null], metadata: [analysis_id: db_meta.analysis_id, model_id: db_meta.model_id]
                                    ], results)
                                }
                                annotation_terminal_records = PEAK_ANNOTATION.out.artifacts
                                    .combine(full_marks_bundle_ch)
                                    .map { annotation_meta, directory, mark_bundle ->
                                    def marks = mark_bundle.values
                                    tuple([
                                        artifact_id: "${annotation_meta.id}.peak_gene_associations", artifact_type: 'peak_gene_annotation', assay: 'chipseq',
                                        format: 'tsv', entity_level: 'peak', contrast_id: null, sample_ids: [], condition: null,
                                        stage: null, mark_or_factor: null, marks_or_factors: marks, peak_type: null,
                                        role: 'peak_gene_associations', producer_manifest_id: annotation_meta.id, producer_process: 'PEAK_ANNOTATION_AGGREGATE',
                                        location: [kind: 'producer_relative', path: 'peak_gene_associations.tsv', base_path: null, producer_manifest_id: annotation_meta.id],
                                        source: [type: 'helixforge', name: params.chipseq_annotation_provider, version: '1.0'], metadata: [:]
                                    ], file("${directory}/peak_gene_associations.tsv", checkIfExists: true))
                                }
                                track_terminal_records = TRACK_GENERATION.out.artifacts
                                    .combine(full_marks_bundle_ch)
                                    .map { track_meta, directory, mark_bundle ->
                                    def marks = mark_bundle.values
                                    tuple([
                                        artifact_id: "${track_meta.id}.signal_tracks", artifact_type: 'signal_track', assay: 'chipseq',
                                        format: 'directory', entity_level: 'sample', contrast_id: null, sample_ids: [], condition: null,
                                        stage: null, mark_or_factor: null, marks_or_factors: marks, peak_type: null,
                                        role: 'visualization', producer_manifest_id: track_meta.id, producer_process: 'TRACK_AGGREGATE',
                                        location: [kind: 'producer_relative', path: 'tracks', base_path: null, producer_manifest_id: track_meta.id],
                                        source: [type: 'helixforge', name: params.chipseq_track_provider, version: '1.0'], metadata: [integration_role: 'visualization']
                                    ], file("${directory}/tracks", checkIfExists: true))
                                }
                                report_terminal_records = CHIPSEQ_REPORT.out.artifacts.map { report_meta, directory ->
                                    tuple([
                                        artifact_id: "${report_meta.id}.report", artifact_type: 'chipseq_report', assay: 'chipseq',
                                        format: 'directory', entity_level: 'report', contrast_id: null, sample_ids: [], condition: null,
                                        stage: null, mark_or_factor: null, marks_or_factors: [], peak_type: null,
                                        role: 'report', producer_manifest_id: report_meta.id, producer_process: 'REPORT_GENERATOR',
                                        location: [kind: 'producer_relative', path: '.', base_path: null, producer_manifest_id: report_meta.id],
                                        source: [type: 'helixforge', name: params.chipseq_report_provider, version: '1.0'], metadata: [:]
                                    ], directory)
                                }
                                terminal_records = bam_terminal_records
                                    .mix(peak_terminal_records)
                                    .mix(peak_qc_terminal_records)
                                    .mix(consensus_terminal_records)
                                    .mix(db_terminal_records)
                                    .mix(db_contrast_terminal_records)
                                    .mix(annotation_terminal_records)
                                    .mix(track_terminal_records)
                                    .mix(report_terminal_records)
                                terminal_record_bundle = terminal_records.toList().map { collected_records ->
                                    def ordered = collected_records.sort { left, right -> left[0]['artifact_id'] <=> right[0]['artifact_id'] }
                                    tuple(
                                        'terminal_manifest',
                                        ordered.collect { value -> value[1] },
                                        groovy.json.JsonOutput.toJson(ordered.collect { value -> value[0] }).bytes.encodeBase64().toString()
                                    )
                                }
                                terminal_source_manifests_ch = full_manifest_files_ch.toList().map { manifests -> tuple('terminal_manifest', manifests) }
                                terminal_metadata_ch = active_plan.map { plan -> tuple('terminal_manifest', plan) }
                                terminal_reference_manifest_ch = reference_bundle_artifacts_ch.map { _meta, _reference, _annotation, manifest -> tuple('terminal_manifest', manifest) }
                                terminal_inputs = terminal_record_bundle
                                    .join(terminal_source_manifests_ch)
                                    .join(terminal_metadata_ch)
                                    .join(terminal_reference_manifest_ch)
                                    .map { _key, artifacts, descriptors, manifests, metadata, reference_manifest ->
                                        def safe_run = workflow.runName.replaceAll(/[^A-Za-z0-9._-]+/, '_')
                                        def manifest_meta = [id: "${safe_run}.chipseq", assay: 'chipseq']
                                        def run = [
                                            id: manifest_meta.id, run_id: workflow.sessionId.toString(), run_name: workflow.runName,
                                            helixforge_version: workflow.manifest.version ?: 'unknown', git_commit: workflow.commitId ?: 'unknown',
                                            nextflow_version: workflow.nextflow.version.toString(), profile: workflow.profile ?: '',
                                            source: [type: 'helixforge', name: 'HelixForge', version: workflow.manifest.version ?: 'unknown'],
                                            parameters: [chipseq_run_mode: mode, differential_binding: db_enabled ? 'requested' : 'not_requested', postprocess: complete_outputs]
                                        ]
                                        def run_base64 = groovy.json.JsonOutput.toJson(run).bytes.encodeBase64().toString()
                                        tuple(manifest_meta, metadata, reference_manifest,
                                            file("${projectDir}/schemas/integration", checkIfExists: true), manifests, artifacts,
                                            db_spec_file, run_base64, descriptors)
                                    }
                                RUN_MANIFEST(terminal_inputs)
                                terminal_manifest_ch = RUN_MANIFEST.out.artifacts
                                terminal_bundle_ch = RUN_MANIFEST.out.bundle
                                full_reports_ch = full_reports_ch.mix(RUN_MANIFEST.out.reports)
                            }
                    }
                }
            }
        }
    }

    completed_ch = complete_outputs \
        ? full_status_ch \
        : (mode == 'qc' \
        ? MULTIQC.out.status \
        : (mode == 'differential_binding' \
            ? differential_binding_status_ch \
            : (mode in ['consensus', 'idr'] \
            ? consolidation_status_ch \
            : (mode == 'peak_qc' \
            ? peak_qc_status_ch \
            : (mode == 'peaks' ? peak_status_ch : (mode == 'post_alignment' ? bam_status_ch : alignment_status_ch))))))

    emit:
    completed           = completed_ch
    execution_plan      = CHIPSEQ_EXECUTION_PLAN.out.manifest
    metadata            = CHIPSEQ_METADATA.out.reports
    qc_reports          = FASTQC.out.reports.mix(MULTIQC.out.reports).mix(post_qc_reports_ch).mix(trimming_reports_ch)
    trimming_manifests  = trimming_manifests_ch
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
    differential_binding = differential_binding_artifacts_ch
    differential_binding_manifest = differential_binding_manifest_ch
    differential_binding_reports = differential_binding_reports_ch
    reference_bundles   = reference_bundle_artifacts_ch
    peak_annotations    = full_annotation_artifacts_ch
    peak_annotation_manifest = full_annotation_manifest_ch
    tracks              = full_track_artifacts_ch
    track_manifest      = full_track_manifest_ch
    report              = full_report_artifacts_ch
    terminal_manifest   = terminal_manifest_ch
    terminal_bundle     = terminal_bundle_ch
    logs                = CHIPSEQ_CONTEXT.out.reports
        .mix(CHIPSEQ_EXECUTION_PLAN.out.reports)
        .mix(CHIPSEQ_METADATA.out.reports.map { metadata_meta, _normalized, _controls, _report, log -> tuple(metadata_meta, log) })
        .mix(FASTQC.out.reports.map { fastqc_meta, _html, log -> tuple(fastqc_meta, log) })
        .mix(post_qc_reports_ch.map { fastqc_meta, _html, log -> tuple(fastqc_meta, log) })
        .mix(trimming_logs_ch)
        .mix(MULTIQC.out.reports.map { multiqc_meta, _html, log -> tuple(multiqc_meta, log) })
        .mix(reference_bundle_reports_ch)
        .mix(full_reports_ch)
}
