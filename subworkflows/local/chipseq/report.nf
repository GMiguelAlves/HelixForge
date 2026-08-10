include { REPORT_CONTEXT } from '../../../modules/local/report_context/main'
include { REPORT_AGGREGATE } from '../../../modules/local/report_aggregate/main'
include { REPORT_GENERATOR } from '../../../modules/local/report_generator/main'


workflow CHIPSEQ_REPORT {
    take:
    report_records

    main:
    sources = report_records.map { meta, _inventory, manifests, semantic_artifacts, presentation ->
        tuple(meta.id, meta, manifests, semantic_artifacts, presentation)
    }
    context_inputs = report_records.map { meta, inventory, manifests, _semantic_artifacts, _presentation ->
        tuple(meta, inventory, manifests)
    }
    REPORT_CONTEXT(context_inputs)

    aggregate_inputs = sources
        .join(REPORT_CONTEXT.out.artifacts.map { meta, context -> tuple(meta.id, context) })
        .map { _id, meta, manifests, semantic_artifacts, _presentation, context ->
            tuple(meta, context, manifests, semantic_artifacts)
        }
    REPORT_AGGREGATE(aggregate_inputs)

    generator_inputs = sources
        .map { id, meta, _manifests, _semantic_artifacts, presentation -> tuple(id, meta, presentation) }
        .join(REPORT_AGGREGATE.out.artifacts.map { meta, aggregate_dir -> tuple(meta.id, aggregate_dir) })
        .map { _id, meta, presentation, aggregate_dir -> tuple(meta, aggregate_dir, presentation) }
    REPORT_GENERATOR(generator_inputs)

    emit:
    artifacts = REPORT_GENERATOR.out.artifacts
    reports   = REPORT_CONTEXT.out.reports.mix(REPORT_AGGREGATE.out.reports).mix(REPORT_GENERATOR.out.reports)
    versions  = REPORT_CONTEXT.out.versions.mix(REPORT_AGGREGATE.out.versions).mix(REPORT_GENERATOR.out.versions)
    status    = REPORT_GENERATOR.out.status
}
