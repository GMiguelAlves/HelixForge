include { TRACK_CONTEXT } from '../../../modules/local/track_context/main'
include { TRACK_PROVIDER } from '../../../modules/local/track_provider/main'
include { TRACK_STATISTICS } from '../../../modules/local/track_statistics/main'
include { TRACK_AGGREGATE } from '../../../modules/local/track_aggregate/main'


workflow TRACK_GENERATION {
    take:
    track_inputs

    main:
    track_records = track_inputs.toList().flatMap { records ->
        def ids = records.collect { record -> record[0].id }
        def collisions = ids.countBy { value -> value }.findAll { _id, count -> count > 1 }.keySet()
        if (collisions) {
            error "Track output-ID collision: ${collisions.sort().join(', ')}"
        }
        records
    }
    TRACK_CONTEXT(track_records)

    sources = track_records.map { meta, bams, bais, _manifests, _reference, _reference_manifest, _spec ->
        tuple(meta.id, meta, bams, bais)
    }
    provider_inputs = TRACK_CONTEXT.out.artifacts
        .map { meta, request -> tuple(meta.id, request) }
        .join(sources)
        .map { _id, request, meta, bams, bais -> tuple(meta, bams, bais, request) }
    TRACK_PROVIDER(provider_inputs)

    statistics_inputs = TRACK_PROVIDER.out.artifacts
        .map { meta, directory -> tuple(meta.id, meta, directory) }
        .join(TRACK_PROVIDER.out.manifest.map { meta, manifest -> tuple(meta.id, manifest) })
        .map { _id, meta, directory, manifest -> tuple(meta, directory, manifest) }
    TRACK_STATISTICS(statistics_inputs)

    aggregate_inputs = TRACK_PROVIDER.out.artifacts
        .map { _meta, directory -> directory }
        .collect()
        .combine(TRACK_PROVIDER.out.manifest.map { _meta, manifest -> manifest }.collect())
        .combine(TRACK_STATISTICS.out.artifacts.map { _meta, statistics_json, _statistics_tsv -> statistics_json }.collect())
        .combine(TRACK_STATISTICS.out.manifest.map { _meta, manifest -> manifest }.collect())
        .map { directories, manifests, statistics, statistics_manifests ->
            tuple([id: 'chipseq.tracks.aggregate'], directories, manifests, statistics, statistics_manifests)
        }
    TRACK_AGGREGATE(aggregate_inputs)

    emit:
    artifacts          = TRACK_AGGREGATE.out.artifacts
    provider_artifacts = TRACK_PROVIDER.out.artifacts
    manifests          = TRACK_PROVIDER.out.manifest
    reports            = TRACK_CONTEXT.out.reports
        .mix(TRACK_PROVIDER.out.reports)
        .mix(TRACK_STATISTICS.out.reports)
        .mix(TRACK_AGGREGATE.out.reports)
    versions           = TRACK_CONTEXT.out.versions
        .mix(TRACK_PROVIDER.out.versions)
        .mix(TRACK_STATISTICS.out.versions)
        .mix(TRACK_AGGREGATE.out.versions)
    manifest           = TRACK_AGGREGATE.out.manifest
    status             = TRACK_AGGREGATE.out.status
}
