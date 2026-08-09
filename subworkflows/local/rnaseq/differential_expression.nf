include { LEGACY_STEP as RNASEQ_BATCH_STEP }  from '../../../modules/local/legacy_step/main'
include { LEGACY_STEP as RNASEQ_DEG_STEP }    from '../../../modules/local/legacy_step/main'
include { LEGACY_STEP as RNASEQ_REPORT_STEP } from '../../../modules/local/legacy_step/main'
include { RNASEQ_DE_CONTEXT }                  from '../../../modules/local/rnaseq_de_context/main'
include { DIFFERENTIAL_EXPRESSION }            from '../differential_expression/differential_expression'

workflow RNASEQ_DIFFERENTIAL_EXPRESSION {
    take:
    config_file
    legacy_root
    quantification_status
    import_manifest
    imported_counts
    imported_metadata

    main:
    no_dep = channel.value('none')

    native_de_enabled = params.rnaseq_native_de instanceof Boolean \
        ? params.rnaseq_native_de \
        : params.rnaseq_native_de.toString().toBoolean()
    native_logs = channel.empty()
    batch_logs = channel.empty()
    if (native_de_enabled) {
        if (!params.rnaseq_de_spec) {
            error 'Native differential expression requires --rnaseq_de_spec with an explicit design and contrasts.'
        }
        de_spec_file = file(params.rnaseq_de_spec, checkIfExists: true)
        RNASEQ_DE_CONTEXT(config_file, legacy_root, de_spec_file)
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
        native_logs = RNASEQ_DE_CONTEXT.out.log.mix(DIFFERENTIAL_EXPRESSION.out.reports)
    } else {
        RNASEQ_BATCH_STEP(
            'rnaseq', 'batch', 'medium', config_file, legacy_root,
            quantification_status, no_dep, no_dep
        )
        RNASEQ_DEG_STEP(
            'rnaseq', 'deg', 'high_cpu', config_file, legacy_root,
            RNASEQ_BATCH_STEP.out.status, no_dep, no_dep
        )
        deg_status = RNASEQ_DEG_STEP.out.status
        native_logs = RNASEQ_DEG_STEP.out.log
        batch_logs = RNASEQ_BATCH_STEP.out.log
    }
    RNASEQ_REPORT_STEP(
        'rnaseq', 'report', 'medium', config_file, legacy_root,
        deg_status, no_dep, no_dep
    )

    emit:
    status = RNASEQ_REPORT_STEP.out.status
    logs   = batch_logs.mix(native_logs)
        .mix(RNASEQ_REPORT_STEP.out.log)
}
