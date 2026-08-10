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

    aggregate_records = TRACK_PROVIDER.out.artifacts
        .map { meta, directory -> tuple(meta.id, directory) }
        .join(TRACK_PROVIDER.out.manifest.map { meta, manifest -> tuple(meta.id, manifest) })
        .join(TRACK_STATISTICS.out.artifacts.map { meta, statistics_json, _statistics_tsv -> tuple(meta.id, statistics_json) })
        .join(TRACK_STATISTICS.out.manifest.map { meta, manifest -> tuple(meta.id, manifest) })
    aggregate_inputs = aggregate_records.toList()
        .map { records ->
            tuple(
                [id: 'chipseq.tracks.aggregate'],
                records.collect { record -> record[1] },
                records.collect { record -> record[2] },
                records.collect { record -> record[3] },
                records.collect { record -> record[4] }
            )
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
