include { LEGACY_STEP as RNASEQ_ANALYSIS_FALLBACK_STEP } from '../../../modules/local/legacy_step/main'
include { RNASEQ_ALIGNMENT_PLAN }                       from '../../../modules/local/rnaseq_alignment_plan/main'
include { RNASEQ_QUANTIFICATION_PLAN }                  from '../../../modules/local/rnaseq_quantification_plan/main'
include { RNASEQ_IMPORT_CONTEXT }                       from '../../../modules/local/rnaseq_import_context/main'
include { REFERENCE_INDEX }                             from '../alignment/reference_index'
include { ALIGNMENT }                                   from '../alignment/alignment'
include { TRANSCRIPTOME_INDEX }                         from '../quantification/transcriptome_index'
include { QUANTIFICATION }                              from '../quantification/quantification'
include { IMPORT }                                      from '../import/import'

workflow RNASEQ_ALIGNMENT_QUANTIFICATION {
    take:
    config_file
    legacy_root
    reference_status
    qc_status
    qc_plans

    main:
    analysis_mode = params.rnaseq_analysis_mode.toString().toLowerCase()
    if (!(analysis_mode in ['config', 'alignment', 'quantification', 'both'])) {
        error "Invalid rnaseq_analysis_mode '${params.rnaseq_analysis_mode}'. Use config, alignment, quantification, or both."
    }

    native_alignment_enabled = params.rnaseq_native_alignment instanceof Boolean \
        ? params.rnaseq_native_alignment \
        : params.rnaseq_native_alignment.toString().toBoolean()
    native_quantification_enabled = params.rnaseq_native_quantification instanceof Boolean \
        ? params.rnaseq_native_quantification \
        : params.rnaseq_native_quantification.toString().toBoolean()
    native_import_enabled = params.rnaseq_native_import instanceof Boolean \
        ? params.rnaseq_native_import \
        : params.rnaseq_native_import.toString().toBoolean()

    if (analysis_mode in ['alignment', 'both'] && !native_alignment_enabled) {
        error "rnaseq_analysis_mode=${analysis_mode} requires rnaseq_native_alignment=true"
    }
    if (analysis_mode in ['quantification', 'both'] && !native_quantification_enabled) {
        error "rnaseq_analysis_mode=${analysis_mode} requires rnaseq_native_quantification=true"
    }
    if (analysis_mode != 'alignment' && !native_import_enabled) {
        error 'rnaseq_native_import=false is no longer supported because the tximport wrapper has been removed.'
    }

    RNASEQ_ALIGNMENT_PLAN(
        config_file,
        legacy_root,
        qc_plans,
        reference_status,
        qc_status
    )
    RNASEQ_QUANTIFICATION_PLAN(
        config_file,
        legacy_root,
        qc_plans,
        reference_status,
        qc_status
    )

    alignment_settings_rows = RNASEQ_ALIGNMENT_PLAN.out.settings
        .splitCsv(header: true, sep: '\t')
    quantification_settings_rows = RNASEQ_QUANTIFICATION_PLAN.out.settings
        .splitCsv(header: true, sep: '\t')

    provider_status = channel.empty()
    provider_logs = RNASEQ_ALIGNMENT_PLAN.out.log
        .mix(RNASEQ_QUANTIFICATION_PLAN.out.log)
    alignment_bam = channel.empty()
    alignment_gene_counts = channel.empty()
    alignment_manifest = channel.empty()
    quantification_table = channel.empty()
    quantification_manifest = channel.empty()
    imported_counts = channel.empty()
    imported_abundance = channel.empty()
    import_manifest = channel.empty()

    if (native_alignment_enabled) {
        star_settings = alignment_settings_rows
            .filter { row -> row.method == 'star' && row.enabled.toBoolean() }

        star_index_inputs = star_settings
            .map { row ->
                def safe_reference = file(row.reference).baseName.replaceAll(/[^A-Za-z0-9_.-]/, '_')
                def index_key = row.index_dir
                def meta = [
                    id        : "star.${safe_reference}.index",
                    aligner   : 'star',
                    index_key : index_key,
                    target_dir: row.index_dir
                ]
                def index_params = [
                    genome_sa_index_nbases   : row.genome_sa_index_nbases,
                    limit_genome_generate_ram: row.limit_genome_generate_ram
                ]
                tuple(
                    meta,
                    file(row.reference, checkIfExists: true),
                    file(row.annotation, checkIfExists: true),
                    index_params
                )
            }
            .unique { item -> item[0].index_key }

        REFERENCE_INDEX(star_index_inputs)

        star_settings_by_project = star_settings.map { row -> tuple(row.project, row) }
        star_samples_by_project = RNASEQ_ALIGNMENT_PLAN.out.plans
            .splitCsv(header: true)
            .map { row -> tuple(row.dataset, row) }

        star_sample_specs = star_samples_by_project
            .combine(star_settings_by_project, by: 0)
            .map { project, sample, settings ->
                def safe_dataset = project.replaceAll(/[^A-Za-z0-9_.-]/, '_')
                def safe_sample = sample.sample_id.replaceAll(/[^A-Za-z0-9_.-]/, '_')
                def meta = [
                    id        : "${safe_dataset}.${safe_sample}.alignment",
                    aligner   : 'star',
                    dataset   : project,
                    sample_id : sample.sample_id,
                    single_end: false,
                    index_key : settings.index_dir,
                    target_dir: sample.star_dir
                ]
                def reads = [
                    file(sample.merged_sample_r1, checkIfExists: true),
                    file(sample.merged_sample_r2, checkIfExists: true)
                ]
                def alignment_params = [
                    read_files_command: settings.read_files_command,
                    extra_args        : settings.extra_args
                ]
                tuple(meta, reads, file(settings.reference, checkIfExists: true),
                    file(settings.annotation, checkIfExists: true), alignment_params)
            }

        star_samples_by_index = star_sample_specs.map { meta, reads, reference, annotation, alignment_params ->
            tuple(meta.index_key, meta, reads, reference, annotation, alignment_params)
        }
        star_indexes_by_key = REFERENCE_INDEX.out.artifacts.map { index_meta, index ->
            tuple(index_meta.index_key, index)
        }
        star_alignment_inputs = star_samples_by_index
            .combine(star_indexes_by_key, by: 0)
            .map { _index_key, meta, reads, reference, annotation, alignment_params, index ->
                tuple(meta, reads, reference, annotation, index, alignment_params)
            }

        ALIGNMENT(star_alignment_inputs)

        provider_status = provider_status.mix(
            ALIGNMENT.out.status.map { _meta, status -> tuple('star', status) }
        )
        provider_logs = provider_logs
            .mix(REFERENCE_INDEX.out.reports)
            .mix(ALIGNMENT.out.logs)
        alignment_bam = ALIGNMENT.out.aligned_bam
        alignment_gene_counts = ALIGNMENT.out.gene_counts
        alignment_manifest = ALIGNMENT.out.manifest
    }

    if (native_quantification_enabled) {
        salmon_settings = quantification_settings_rows
            .filter { row -> row.method == 'salmon' && row.enabled.toBoolean() }

        salmon_index_inputs = salmon_settings
            .map { row ->
                def safe_transcriptome = file(row.transcriptome).baseName.replaceAll(/[^A-Za-z0-9_.-]/, '_')
                def index_key = row.index_dir
                def meta = [
                    id        : "salmon.${safe_transcriptome}.index",
                    quantifier: 'salmon',
                    index_key : index_key,
                    target_dir: row.index_dir
                ]
                tuple(
                    meta,
                    file(row.transcriptome, checkIfExists: true),
                    [kmer_size: row.kmer_size]
                )
            }
            .unique { item -> item[0].index_key }

        TRANSCRIPTOME_INDEX(salmon_index_inputs)

        salmon_settings_by_project = salmon_settings.map { row -> tuple(row.project, row) }
        salmon_samples_by_project = RNASEQ_QUANTIFICATION_PLAN.out.plans
            .splitCsv(header: true)
            .map { row -> tuple(row.dataset, row) }

        salmon_sample_specs = salmon_samples_by_project
            .combine(salmon_settings_by_project, by: 0)
            .map { project, sample, settings ->
                def safe_dataset = project.replaceAll(/[^A-Za-z0-9_.-]/, '_')
                def safe_sample = sample.sample_id.replaceAll(/[^A-Za-z0-9_.-]/, '_')
                def meta = [
                    id        : "${safe_dataset}.${safe_sample}.quantification",
                    quantifier: 'salmon',
                    dataset   : project,
                    sample_id : sample.sample_id,
                    single_end: false,
                    index_key : settings.index_dir,
                    target_dir: sample.quant_dir
                ]
                def reads = [
                    file(sample.merged_sample_r1, checkIfExists: true),
                    file(sample.merged_sample_r2, checkIfExists: true)
                ]
                def quantification_params = [
                    lib_type         : settings.lib_type,
                    validate_mappings: settings.validate_mappings.toBoolean()
                ]
                tuple(meta, reads, file(settings.transcriptome, checkIfExists: true), quantification_params)
            }

        salmon_samples_by_index = salmon_sample_specs.map { meta, reads, transcriptome, quantification_params ->
            tuple(meta.index_key, meta, reads, transcriptome, quantification_params)
        }
        salmon_indexes_by_key = TRANSCRIPTOME_INDEX.out.artifacts.map { index_meta, index ->
            tuple(index_meta.index_key, index)
        }
        salmon_quantification_inputs = salmon_samples_by_index
            .combine(salmon_indexes_by_key, by: 0)
            .map { _index_key, meta, reads, transcriptome, quantification_params, index ->
                tuple(meta, reads, transcriptome, index, quantification_params)
            }

        QUANTIFICATION(salmon_quantification_inputs)

        provider_status = provider_status.mix(
            QUANTIFICATION.out.status.map { _meta, status -> tuple('salmon', status) }
        )
        provider_logs = provider_logs
            .mix(TRANSCRIPTOME_INDEX.out.reports)
            .mix(QUANTIFICATION.out.logs)
        quantification_table = QUANTIFICATION.out.quantification
        quantification_manifest = QUANTIFICATION.out.manifest
    }

    fallback_status = channel.empty()
    fallback_logs = channel.empty()
    if (!native_alignment_enabled || !native_quantification_enabled) {
        legacy_gate = channel.empty()
        if (!native_alignment_enabled) {
            legacy_gate = legacy_gate.mix(
                alignment_settings_rows
                    .filter { row -> row.enabled.toBoolean() }
                    .map { row -> row.method }
            )
        }
        if (!native_quantification_enabled) {
            legacy_gate = legacy_gate.mix(
                quantification_settings_rows
                    .filter { row -> row.enabled.toBoolean() }
                    .map { row -> row.method }
            )
        }

        RNASEQ_ANALYSIS_FALLBACK_STEP(
            'rnaseq', 'salmon', 'high_cpu', config_file, legacy_root,
            reference_status, qc_status, legacy_gate
        )
        fallback_status = RNASEQ_ANALYSIS_FALLBACK_STEP.out.status
        fallback_logs = RNASEQ_ANALYSIS_FALLBACK_STEP.out.log
    }

    if (analysis_mode == 'alignment') {
        completion_status = provider_status
            .map { _provider, status -> status }
            .mix(fallback_status)
            .collect()
        completion_logs = provider_logs.mix(fallback_logs)
    } else {
        import_method = analysis_mode == 'quantification' \
            ? channel.value('salmon') \
            : quantification_settings_rows
                .map { row -> row.configured_method }
                .unique()
                .first()

        salmon_artifacts_by_id = quantification_table.map { meta, artifact ->
            tuple(meta.id, meta, artifact)
        }
        salmon_manifests_by_id = quantification_manifest.map { meta, manifest ->
            tuple(meta.id, manifest)
        }
        salmon_import_sources = salmon_artifacts_by_id
            .combine(salmon_manifests_by_id, by: 0)
            .map { _id, provider_meta, artifact, manifest ->
                def source_meta = provider_meta + [provider: 'salmon']
                tuple(source_meta, manifest, artifact, 'quantification')
            }

        star_artifacts_by_id = alignment_gene_counts.map { meta, artifact ->
            tuple(meta.id, meta, artifact)
        }
        star_manifests_by_id = alignment_manifest.map { meta, manifest ->
            tuple(meta.id, manifest)
        }
        star_import_sources = star_artifacts_by_id
            .combine(star_manifests_by_id, by: 0)
            .map { _id, provider_meta, artifact, manifest ->
                def source_meta = provider_meta + [provider: 'star']
                tuple(source_meta, manifest, artifact, 'gene_counts')
            }

        selected_import_sources = salmon_import_sources
            .mix(star_import_sources)
            .combine(import_method)
            .filter { _meta, _manifest, _artifact, _role, method ->
                _meta.provider == method
            }
            .map { meta, manifest, artifact, role, _method ->
                tuple(meta, manifest, artifact, role)
            }

        RNASEQ_IMPORT_CONTEXT(
            config_file,
            legacy_root,
            import_method,
            native_alignment_enabled,
            native_quantification_enabled
        )
        import_context = RNASEQ_IMPORT_CONTEXT.out.settings
            .splitCsv(header: true, sep: '\t')
            .combine(RNASEQ_IMPORT_CONTEXT.out.metadata)
            .combine(RNASEQ_IMPORT_CONTEXT.out.annotation)

        salmon_context = import_context
            .filter { row, _metadata, _annotation -> row.provider == 'salmon' }
            .map { row, metadata, annotation ->
                def meta = [
                    id        : 'rnaseq.import',
                    provider  : 'salmon',
                    target_dir: row.target_dir
                ]
                def import_params = [
                    project          : '',
                    allow_missing    : false,
                    star_count_column: row.star_count_column,
                    countsFromAbundance: 'no',
                    ignoreTxVersion  : true,
                    ignoreAfterBar   : true
                ]
                tuple(meta, metadata, annotation, import_params)
            }
        star_context = import_context
            .filter { row, _metadata, _annotation -> row.provider == 'star' }
            .map { row, metadata, _annotation ->
                def meta = [
                    id        : 'rnaseq.import',
                    provider  : 'star',
                    target_dir: row.target_dir
                ]
                def import_params = [
                    project          : '',
                    allow_missing    : false,
                    star_count_column: row.star_count_column
                ]
                tuple(meta, metadata, import_params)
            }

        IMPORT(selected_import_sources, salmon_context, star_context)
        completion_status = IMPORT.out.status.collect()
        completion_logs = provider_logs
            .mix(fallback_logs)
            .mix(RNASEQ_IMPORT_CONTEXT.out.log)
            .mix(IMPORT.out.reports)
        imported_counts = IMPORT.out.counts
        imported_abundance = IMPORT.out.abundance
        import_manifest = IMPORT.out.manifest
    }

    emit:
    status                  = completion_status
    logs                    = completion_logs
    aligned_bam             = alignment_bam
    quantification          = quantification_table
    quantification_manifest = quantification_manifest
    imported_counts         = imported_counts
    imported_abundance      = imported_abundance
    import_manifest         = import_manifest
}
