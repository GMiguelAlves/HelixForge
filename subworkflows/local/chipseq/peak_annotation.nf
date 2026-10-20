include { PEAK_ANNOTATION_CONTEXT } from '../../../modules/local/peak_annotation_context/main'
include { PEAK_ANNOTATOR } from '../../../modules/local/peak_annotator/main'
include { PEAK_ANNOTATION_STATISTICS } from '../../../modules/local/peak_annotation_statistics/main'
include { PEAK_ANNOTATION_AGGREGATE } from '../../../modules/local/peak_annotation_aggregate/main'
include { HOMER_ANNOTATEPEAKS } from '../../../modules/local/homer_annotatepeaks/main'
include { HOMER_ANNOTATION_ADAPTER } from '../../../modules/local/homer_annotation_adapter/main'


workflow PEAK_ANNOTATION {
    take:
    annotation_inputs

    main:
    annotation_records = annotation_inputs.toList().flatMap { records ->
        if (records.any { record -> !(record.size() in [7, 8]) }) {
            error 'Annotation inputs require seven fields plus an optional declared evidence-directory list'
        }
        def ids = records.collect { record -> record[0].id }
        def collisions = ids.countBy { value -> value }.findAll { _id, count -> count > 1 }.keySet()
        if (collisions) {
            error "Peak annotation output-ID collision: ${collisions.sort().join(', ')}"
        }
        records
    }
    context_records = annotation_records.map { row -> tuple(row[0], row[1], row[2], row[3], row[4], row[5], row[6]) }
    PEAK_ANNOTATION_CONTEXT(context_records, file("${moduleDir}/../../../modules/local/peak_annotation_context/resources/usr/bin/validate_peak_annotation_context.py", checkIfExists: true))

    sources = annotation_records.map { row ->
        tuple(row[0].id, row[0], row[1], row[3], row[5], row.size() == 8 ? row[7] : [])
    }
    provider_inputs = PEAK_ANNOTATION_CONTEXT.out.artifacts
        .map { meta, request -> tuple(meta.id, request) }
        .join(sources)
        .map { _id, request, meta, peaks, reference, annotation, evidence -> tuple(meta, peaks, reference, annotation, request, evidence) }
    provider_artifacts = channel.empty()
    provider_manifests = channel.empty()
    provider_reports = channel.empty()
    provider_versions = channel.empty()
    if (params.chipseq_annotation_provider == 'homer_4_11') {
        HOMER_ANNOTATEPEAKS(provider_inputs.map { meta, peaks, reference, annotation, request, _evidence -> tuple(meta, peaks, reference, annotation, request) })
        adapter_inputs = HOMER_ANNOTATEPEAKS.out.artifacts.map { meta, raw -> tuple(meta.id, raw) }
            .join(provider_inputs.map { meta, peaks, _reference, _annotation, request, evidence -> tuple(meta.id, meta, peaks, request, evidence) })
            .map { _id, raw, meta, peaks, request, evidence -> tuple(meta, peaks, request, raw, evidence) }
        HOMER_ANNOTATION_ADAPTER(adapter_inputs, file("${moduleDir}/../../../modules/local/homer_annotation_adapter/resources/usr/bin/normalize_homer.py", checkIfExists: true))
        provider_artifacts = HOMER_ANNOTATION_ADAPTER.out.artifacts
        provider_manifests = HOMER_ANNOTATION_ADAPTER.out.manifest
        provider_reports = HOMER_ANNOTATION_ADAPTER.out.reports
        provider_versions = HOMER_ANNOTATEPEAKS.out.versions.mix(HOMER_ANNOTATION_ADAPTER.out.versions)
    } else {
        PEAK_ANNOTATOR(provider_inputs.map { meta, peaks, _reference, annotation, request, _evidence -> tuple(meta, peaks, annotation, request) }, file("${moduleDir}/../../../modules/local/peak_annotator/resources/usr/bin/run_peak_annotator.py", checkIfExists: true))
        provider_artifacts = PEAK_ANNOTATOR.out.artifacts
        provider_manifests = PEAK_ANNOTATOR.out.manifest
        provider_reports = PEAK_ANNOTATOR.out.reports
        provider_versions = PEAK_ANNOTATOR.out.versions
    }

    provider_by_id = provider_artifacts
        .map { meta, directory -> tuple(meta.id, meta, directory) }
        .join(provider_manifests.map { meta, manifest -> tuple(meta.id, manifest) })
        .map { _id, meta, directory, manifest -> tuple(meta, directory, manifest) }
    PEAK_ANNOTATION_STATISTICS(provider_by_id, file("${moduleDir}/../../../modules/local/peak_annotation_statistics/resources/usr/bin/peak_annotation_statistics.py", checkIfExists: true))

    aggregate_records = provider_artifacts
        .map { meta, directory -> tuple(meta.id, directory) }
        .join(provider_manifests.map { meta, manifest -> tuple(meta.id, manifest) })
        .join(PEAK_ANNOTATION_STATISTICS.out.artifacts.map { meta, statistics_json, _statistics_tsv -> tuple(meta.id, statistics_json) })
        .join(PEAK_ANNOTATION_STATISTICS.out.manifest.map { meta, manifest -> tuple(meta.id, manifest) })
    aggregate_inputs = aggregate_records.toList()
        .map { records ->
            tuple(
                [id: 'chipseq.peak_annotation.aggregate'],
                records.collect { record -> record[1] },
                records.collect { record -> record[2] },
                records.collect { record -> record[3] },
                records.collect { record -> record[4] }
            )
        }
    PEAK_ANNOTATION_AGGREGATE(aggregate_inputs, file("${moduleDir}/../../../modules/local/peak_annotation_aggregate/resources/usr/bin/peak_annotation_aggregate.py", checkIfExists: true))

    emit:
    artifacts          = PEAK_ANNOTATION_AGGREGATE.out.artifacts
    provider_artifacts = provider_artifacts
    manifests          = provider_manifests
    reports            = PEAK_ANNOTATION_CONTEXT.out.reports
        .mix(provider_reports)
        .mix(PEAK_ANNOTATION_STATISTICS.out.reports)
        .mix(PEAK_ANNOTATION_AGGREGATE.out.reports)
    versions           = PEAK_ANNOTATION_CONTEXT.out.versions
        .mix(provider_versions)
        .mix(PEAK_ANNOTATION_STATISTICS.out.versions)
        .mix(PEAK_ANNOTATION_AGGREGATE.out.versions)
    manifest           = PEAK_ANNOTATION_AGGREGATE.out.manifest
    status             = PEAK_ANNOTATION_AGGREGATE.out.status
}
