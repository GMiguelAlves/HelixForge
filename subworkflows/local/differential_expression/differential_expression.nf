include { DE_PREFLIGHT }    from '../../../modules/local/de_preflight/main'
include { DESEQ2_MODEL }    from '../../../modules/local/deseq2_model/main'
include { DESEQ2_CONTRAST } from '../../../modules/local/deseq2_contrast/main'
include { DE_AGGREGATE }    from '../../../modules/local/de_aggregate/main'

workflow DIFFERENTIAL_EXPRESSION {
    take:
    requests

    main:
    DE_PREFLIGHT(requests)

    model_inputs = DE_PREFLIGHT.out.models.flatMap { parent_meta, model_specs_dir, _contrast_specs_dir, counts, samples, annotation ->
        model_specs_dir.toFile().listFiles()
            .findAll { path -> path.name.endsWith('.json') }
            .sort { left, right -> left.name <=> right.name }
            .collect { model_spec ->
                def document = new groovy.json.JsonSlurper().parse(model_spec)
                def model_meta = parent_meta + [
                    id        : document.model_id,
                    model_id  : document.model_id,
                    variable  : document.variable,
                    provider  : document.provider,
                    target_dir: document.target_dir
                ]
                tuple(model_meta, counts, samples, file(model_spec), annotation)
            }
    }
    DESEQ2_MODEL(model_inputs)

    contrast_plans = DE_PREFLIGHT.out.models.flatMap { parent_meta, _model_specs_dir, contrast_specs_dir, _counts, _samples, _annotation ->
        contrast_specs_dir.toFile().listFiles()
            .findAll { path -> path.name.endsWith('.json') }
            .sort { left, right -> left.name <=> right.name }
            .collect { contrast_spec ->
                def document = new groovy.json.JsonSlurper().parse(contrast_spec)
                def contrast_meta = parent_meta + [
                    id         : "${document.model_id}.${document.id}",
                    model_id   : document.model_id,
                    contrast_id: document.id,
                    provider   : 'deseq2'
                ]
                tuple(document.model_id, contrast_meta, file(contrast_spec))
            }
    }
    models_by_id = DESEQ2_MODEL.out.artifacts.map { model_meta, model, model_spec, annotation ->
        tuple(model_meta.model_id, model, model_spec, annotation)
    }
    contrast_inputs = models_by_id
        .combine(contrast_plans, by: 0)
        .map { _model_id, model, model_spec, annotation, contrast_meta, contrast_spec ->
            tuple(contrast_meta, model, model_spec, contrast_spec, annotation)
        }
    DESEQ2_CONTRAST(contrast_inputs)

    aggregate_context = DE_PREFLIGHT.out.aggregate_context.map { meta, skipped, analysis_spec ->
        tuple(meta, skipped, analysis_spec)
    }
    model_directories = DESEQ2_MODEL.out.artifacts.map { _meta, model, _spec, _annotation -> model }.collect()
    contrast_directories = DESEQ2_CONTRAST.out.artifacts.map { _meta, contrast -> contrast }.collect()
    DE_AGGREGATE(aggregate_context, model_directories, contrast_directories)

    emit:
    artifacts          = DE_AGGREGATE.out.artifacts
    results            = DE_AGGREGATE.out.results
    significant        = DE_AGGREGATE.out.significant
    common_results     = DE_AGGREGATE.out.common_results
    normalized_counts  = DESEQ2_MODEL.out.artifacts.map { meta, model, _spec, _annotation ->
        tuple(meta, model)
    }
    reports            = DE_PREFLIGHT.out.reports
        .mix(DESEQ2_MODEL.out.reports)
        .mix(DESEQ2_CONTRAST.out.reports)
        .mix(DE_AGGREGATE.out.reports)
    versions           = DE_PREFLIGHT.out.versions
        .mix(DESEQ2_MODEL.out.versions)
        .mix(DESEQ2_CONTRAST.out.versions)
        .mix(DE_AGGREGATE.out.versions)
    execution_metadata = DESEQ2_MODEL.out.execution_metadata
        .mix(DESEQ2_CONTRAST.out.execution_metadata)
        .mix(DE_AGGREGATE.out.execution_metadata)
    manifest           = DE_AGGREGATE.out.manifest
    status             = DE_AGGREGATE.out.status
}
