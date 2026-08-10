include { PEAK_ANNOTATION_CONTEXT } from '../../../modules/local/peak_annotation_context/main'
include { PEAK_ANNOTATOR } from '../../../modules/local/peak_annotator/main'
include { PEAK_ANNOTATION_STATISTICS } from '../../../modules/local/peak_annotation_statistics/main'
include { PEAK_ANNOTATION_AGGREGATE } from '../../../modules/local/peak_annotation_aggregate/main'


workflow PEAK_ANNOTATION {
    take:
    annotation_inputs

    main:
    PEAK_ANNOTATION_CONTEXT(annotation_inputs)

    sources = annotation_inputs.map { meta, peaks, _peak_manifest, _reference, _reference_manifest, annotation, _spec ->
        tuple(meta.id, meta, peaks, annotation)
    }
    provider_inputs = PEAK_ANNOTATION_CONTEXT.out.artifacts
        .map { meta, request -> tuple(meta.id, request) }
        .join(sources)
        .map { _id, request, meta, peaks, annotation -> tuple(meta, peaks, annotation, request) }
    PEAK_ANNOTATOR(provider_inputs)

    provider_by_id = PEAK_ANNOTATOR.out.artifacts
        .map { meta, directory -> tuple(meta.id, meta, directory) }
        .join(PEAK_ANNOTATOR.out.manifest.map { meta, manifest -> tuple(meta.id, manifest) })
        .map { _id, meta, directory, manifest -> tuple(meta, directory, manifest) }
    PEAK_ANNOTATION_STATISTICS(provider_by_id)

    aggregate_inputs = PEAK_ANNOTATOR.out.artifacts
        .map { _meta, directory -> directory }
        .collect()
        .combine(PEAK_ANNOTATOR.out.manifest.map { _meta, manifest -> manifest }.collect())
        .combine(PEAK_ANNOTATION_STATISTICS.out.artifacts.map { _meta, statistics_json, _statistics_tsv -> statistics_json }.collect())
        .combine(PEAK_ANNOTATION_STATISTICS.out.manifest.map { _meta, manifest -> manifest }.collect())
        .map { directories, manifests, statistics, statistics_manifests ->
            tuple([id: 'chipseq.peak_annotation.aggregate'], directories, manifests, statistics, statistics_manifests)
        }
    PEAK_ANNOTATION_AGGREGATE(aggregate_inputs)

    emit:
    artifacts          = PEAK_ANNOTATION_AGGREGATE.out.artifacts
    provider_artifacts = PEAK_ANNOTATOR.out.artifacts
    manifests          = PEAK_ANNOTATOR.out.manifest
    reports            = PEAK_ANNOTATION_CONTEXT.out.reports
        .mix(PEAK_ANNOTATOR.out.reports)
        .mix(PEAK_ANNOTATION_STATISTICS.out.reports)
        .mix(PEAK_ANNOTATION_AGGREGATE.out.reports)
    versions           = PEAK_ANNOTATION_CONTEXT.out.versions
        .mix(PEAK_ANNOTATOR.out.versions)
        .mix(PEAK_ANNOTATION_STATISTICS.out.versions)
        .mix(PEAK_ANNOTATION_AGGREGATE.out.versions)
    manifest           = PEAK_ANNOTATION_AGGREGATE.out.manifest
    status             = PEAK_ANNOTATION_AGGREGATE.out.status
}
