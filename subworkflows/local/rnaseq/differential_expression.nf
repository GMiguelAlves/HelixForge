include { RNASEQ_DE_CONTEXT }                  from '../../../modules/local/rnaseq_de_context/main'
include { DIFFERENTIAL_EXPRESSION }            from '../differential_expression/differential_expression'
include { RNASEQ_REPORT }                      from './report'

workflow RNASEQ_DIFFERENTIAL_EXPRESSION {
    take:
    config_file
    pipeline_root
    quantification_status
    import_manifest
    imported_counts
    imported_abundance
    imported_metadata
    reference_annotation

    main:
    native_de_enabled = params.rnaseq_native_de instanceof Boolean \
        ? params.rnaseq_native_de \
        : params.rnaseq_native_de.toString().toBoolean()
    report_enabled = params.rnaseq_report_enabled instanceof Boolean \
        ? params.rnaseq_report_enabled \
        : params.rnaseq_report_enabled.toString().toBoolean()
    run_mode = params.rnaseq_run_mode.toString().toLowerCase()
    run_report = run_mode == 'report' || (run_mode == 'full' && report_enabled)
    native_logs = channel.empty()
    de_results = channel.empty()
    de_common_results = channel.empty()
    de_manifest = channel.empty()
    de_normalized_counts = channel.empty()
    de_model_manifest = channel.empty()
    de_contrast_results = channel.empty()
    de_contrast_manifest = channel.empty()
    report_artifacts = channel.empty()
    report_manifest = channel.empty()
    if (!native_de_enabled) {
        error 'rnaseq_native_de=false is no longer supported; the RNA-seq legacy pipeline was retired in rnaseq-legacy-v1.0.0.'
    }
    if (native_de_enabled) {
        if (!params.rnaseq_de_spec) {
            error 'Native differential expression requires --rnaseq_de_spec with an explicit design and contrasts.'
        }
        de_spec_file = file(params.rnaseq_de_spec, checkIfExists: true)
        RNASEQ_DE_CONTEXT(config_file, pipeline_root, de_spec_file)
        counts_by_id = imported_counts.map { meta, counts -> tuple(meta.id, meta, counts) }
        manifests_by_id = import_manifest.map { meta, manifest -> tuple(meta.id, manifest) }
        metadata_by_id = imported_metadata.map { meta, metadata -> tuple(meta.id, metadata) }
        import_bundle = counts_by_id
            .combine(manifests_by_id, by: 0)
            .combine(metadata_by_id, by: 0)
        native_requests = import_bundle
            .combine(RNASEQ_DE_CONTEXT.out.analysis_spec)
            .combine(RNASEQ_DE_CONTEXT.out.annotation)
            .map { _import_id, import_meta, counts, manifest, metadata, analysis_spec, annotation ->
                def specification = new groovy.json.JsonSlurper().parse(analysis_spec)
                def meta = [
                    id         : 'rnaseq.de.all_projects_raw',
                    provider   : 'deseq2',
                    analysis_id: specification.analysis_id,
                    target_dir : specification.target_dir,
                    import_id  : import_meta.id
                ]
                tuple(meta, manifest, counts, metadata, analysis_spec, annotation)
            }
        DIFFERENTIAL_EXPRESSION(native_requests)
        deg_status = DIFFERENTIAL_EXPRESSION.out.status
        de_results = DIFFERENTIAL_EXPRESSION.out.results
        de_common_results = DIFFERENTIAL_EXPRESSION.out.common_results
        de_manifest = DIFFERENTIAL_EXPRESSION.out.manifest
        de_normalized_counts = DIFFERENTIAL_EXPRESSION.out.normalized_counts
        de_model_manifest = DIFFERENTIAL_EXPRESSION.out.model_manifest
        de_contrast_results = DIFFERENTIAL_EXPRESSION.out.contrast_results
        de_contrast_manifest = DIFFERENTIAL_EXPRESSION.out.contrast_manifest
        native_logs = RNASEQ_DE_CONTEXT.out.log.mix(DIFFERENTIAL_EXPRESSION.out.reports)

        if (run_report) {
            if (!params.rnaseq_report_genes) {
                error 'RNA-seq Report API requires --rnaseq_report_genes with an explicit candidate-gene group file.'
            }
            if (params.rnaseq_report_provider.toString() != 'candidate_genes_v1') {
                error "Unsupported rnaseq_report_provider '${params.rnaseq_report_provider}'."
            }
            genes_file = file(params.rnaseq_report_genes, checkIfExists: true)
            report_target = params.rnaseq_report_outdir \
                ? params.rnaseq_report_outdir.toString() \
                : "${params.outdir}/rnaseq/090-search-gene"
            report_parameters = [
                title              : params.rnaseq_report_title ?: 'Candidate gene report',
                expression_unit    : params.rnaseq_report_expression_unit ?: 'TPM',
                life_stage_levels  : params.rnaseq_report_life_stage_levels ?: 'unknown',
                stage_synonym_map  : params.rnaseq_report_stage_synonym_map ?: '',
                organism_specific : params.rnaseq_report_organism_specific ?: false
            ]
            report_parameters_base64 = groovy.json.JsonOutput.toJson(report_parameters)
                .bytes.encodeBase64().toString()
            report_sources = imported_abundance
                .combine(imported_metadata)
                .combine(import_manifest)
                .combine(DIFFERENTIAL_EXPRESSION.out.results)
                .combine(DIFFERENTIAL_EXPRESSION.out.manifest)
                .combine(reference_annotation)
                .map { import_meta_a, abundance, _import_meta_s, samples, _import_meta_m, upstream_import_manifest,
                       de_meta_r, de_results_file, _de_meta_m, upstream_de_manifest, annotation ->
                    def meta = [
                        id        : 'rnaseq.report.candidate_genes',
                        provider  : 'candidate_genes_v1',
                        target_dir: report_target,
                        import_id : import_meta_a.id,
                        analysis_id: de_meta_r.analysis_id
                    ]
                    tuple(meta, upstream_import_manifest, abundance, samples, annotation,
                        de_results_file, upstream_de_manifest, genes_file, report_parameters_base64)
                }
            RNASEQ_REPORT(report_sources)
            final_status = RNASEQ_REPORT.out.status
            report_artifacts = RNASEQ_REPORT.out.artifacts
            report_manifest = RNASEQ_REPORT.out.manifest
            native_logs = native_logs.mix(RNASEQ_REPORT.out.reports)
        } else {
            final_status = deg_status
        }
    }

    emit:
    status = final_status
    logs   = native_logs
    results = de_results
    common_results = de_common_results
    manifest = de_manifest
    normalized_counts = de_normalized_counts
    model_manifest = de_model_manifest
    contrast_results = de_contrast_results
    contrast_manifest = de_contrast_manifest
    report_artifacts = report_artifacts
    report_manifest = report_manifest
}
