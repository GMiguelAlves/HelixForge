include { CONSENSUS_CONTEXT } from '../../../modules/local/consensus_context/main'
include { CONSENSUS_INTERVALS as CONSENSUS_UNION } from '../../../modules/local/consensus_intervals/main'
include { CONSENSUS_INTERVALS as CONSENSUS_INTERSECTION } from '../../../modules/local/consensus_intervals/main'
include { CONSENSUS_INTERVALS as CONSENSUS_SUPPORT } from '../../../modules/local/consensus_intervals/main'
include { IDR_PROVIDER } from '../../../modules/local/idr_provider/main'
include { CONSENSUS_AGGREGATE } from '../../../modules/local/consensus_aggregate/main'


workflow CONSENSUS_IDR {
    take:
    peak_artifacts
    peak_manifests
    peak_qc_manifests
    peak_plan
    strategy_spec_base64

    main:
    strategy = params.chipseq_consensus_strategy.toString().toLowerCase()

    peak_records = peak_artifacts
        .map { meta, result_dir -> tuple(meta.id, result_dir) }
        .join(peak_manifests.map { meta, manifest -> tuple(meta.id, manifest) })
        .map { peak_id, result_dir, manifest ->
            def document = new groovy.json.JsonSlurper().parse(manifest.toFile())
            if (document.id != peak_id) {
                error "Peak artifact/manifest identity mismatch for ${peak_id}"
            }
            tuple(document.record_id, peak_id, result_dir, manifest, document)
        }

    qc_records = peak_qc_manifests
        .map { _meta, manifest ->
            def document = new groovy.json.JsonSlurper().parse(manifest.toFile())
            tuple(document.id, manifest, document)
        }
        .filter { _peak_id, _manifest, document -> document.type == 'peak_qc_frip' }

    plan_by_record = peak_plan
        .map { _meta, _validated_plan, plan -> plan }
        .splitCsv(header: true, sep: '\t')
        .map { row -> tuple(row.record_id, row) }

    records_by_peak = peak_records
        .join(plan_by_record)
        .map { record_id, peak_id, result_dir, peak_manifest, peak_document, row ->
            if (peak_document.record_id != record_id || peak_document.sample_id != row.sample_id) {
                error "Unsafe Consensus association for record ${record_id}"
            }
            def group_fields = [
                row.dataset, peak_document.experiment_id, row.condition, peak_document.target,
                row.genome_id, peak_document.peak_type
            ]
            if (group_fields.any { value -> !value }) {
                error "Consensus grouping identity is incomplete for ${peak_id}"
            }
            def group_key = group_fields.join('\u001f')
            def group_id = [row.dataset, row.condition, peak_document.target, row.genome_id, peak_document.peak_type]
                .collect { value -> value.toString().replaceAll(/[^A-Za-z0-9._-]+/, '_') }
                .join('.')
            def record = [
                group_id              : group_id,
                peak_id               : peak_id,
                peak_directory        : result_dir.name,
                record_id             : record_id,
                sample_id             : peak_document.sample_id,
                dataset               : row.dataset,
                experiment_id         : peak_document.experiment_id,
                condition             : row.condition,
                treatment             : row.treatment ?: '',
                target                : peak_document.target,
                control_id            : peak_document.control_id ?: '',
                control_record_id     : peak_document.control_record_id ?: '',
                biological_replicate  : peak_document.biological_replicate,
                technical_replicate   : peak_document.technical_replicate,
                genome_id             : row.genome_id,
                organism              : row.organism,
                peak_type             : peak_document.peak_type,
                caller                : peak_document.caller,
                caller_version        : peak_document.caller_version,
            ]
            tuple(peak_id, group_key, record, result_dir, peak_manifest)
        }

    grouped_base = records_by_peak
        .join(qc_records)
        .map { _peak_id, group_key, record, result_dir, peak_manifest, qc_manifest, _qc_document ->
            tuple(group_key, record, result_dir, peak_manifest, qc_manifest)
        }
        .groupTuple(by: 0)
        .map { _group_key, records, result_dirs, manifests, qc_files ->
            def group_ids = records.collect { record -> record.group_id }.unique()
            if (group_ids.size() != 1) {
                error "Consensus group-id collision: ${group_ids}"
            }
            def meta = [id: group_ids[0], strategy: strategy]
            def recordsBase64 = groovy.json.JsonOutput.toJson(records).getBytes('UTF-8').encodeBase64().toString()
            tuple(meta, result_dirs, manifests, qc_files, recordsBase64)
        }

    context_inputs = grouped_base
        .combine(strategy_spec_base64)
        .map { meta, result_dirs, manifests, qc_files, records_base64, spec ->
            tuple(meta, result_dirs, manifests, qc_files, records_base64, spec)
        }
    CONSENSUS_CONTEXT(context_inputs)

    sources = context_inputs.map { meta, result_dirs, _manifests, _qc_files, _records, _spec ->
        tuple(meta.id, meta, result_dirs)
    }
    validated = CONSENSUS_CONTEXT.out.artifacts
        .map { meta, request -> tuple(meta.id, request) }
        .join(sources)

    provider_artifacts_ch = channel.empty()
    provider_reports_ch = channel.empty()
    provider_versions_ch = channel.empty()
    provider_execution_ch = channel.empty()
    provider_manifest_ch = channel.empty()
    provider_status_ch = channel.empty()
    if (strategy == 'union') {
        provider_inputs = validated.map { _id, request, meta, result_dirs -> tuple(meta, result_dirs, request, 'union') }
        CONSENSUS_UNION(provider_inputs)
        provider_artifacts_ch = CONSENSUS_UNION.out.artifacts
        provider_reports_ch = CONSENSUS_UNION.out.reports
        provider_versions_ch = CONSENSUS_UNION.out.versions
        provider_execution_ch = CONSENSUS_UNION.out.execution_metadata
        provider_manifest_ch = CONSENSUS_UNION.out.manifest
        provider_status_ch = CONSENSUS_UNION.out.status
    } else if (strategy == 'intersection') {
        provider_inputs = validated.map { _id, request, meta, result_dirs -> tuple(meta, result_dirs, request, 'intersection') }
        CONSENSUS_INTERSECTION(provider_inputs)
        provider_artifacts_ch = CONSENSUS_INTERSECTION.out.artifacts
        provider_reports_ch = CONSENSUS_INTERSECTION.out.reports
        provider_versions_ch = CONSENSUS_INTERSECTION.out.versions
        provider_execution_ch = CONSENSUS_INTERSECTION.out.execution_metadata
        provider_manifest_ch = CONSENSUS_INTERSECTION.out.manifest
        provider_status_ch = CONSENSUS_INTERSECTION.out.status
    } else if (strategy == 'replicate_support') {
        provider_inputs = validated.map { _id, request, meta, result_dirs -> tuple(meta, result_dirs, request, 'replicate_support') }
        CONSENSUS_SUPPORT(provider_inputs)
        provider_artifacts_ch = CONSENSUS_SUPPORT.out.artifacts
        provider_reports_ch = CONSENSUS_SUPPORT.out.reports
        provider_versions_ch = CONSENSUS_SUPPORT.out.versions
        provider_execution_ch = CONSENSUS_SUPPORT.out.execution_metadata
        provider_manifest_ch = CONSENSUS_SUPPORT.out.manifest
        provider_status_ch = CONSENSUS_SUPPORT.out.status
    } else if (strategy == 'idr') {
        provider_inputs = validated.map { _id, request, meta, result_dirs -> tuple(meta, result_dirs, request) }
        IDR_PROVIDER(provider_inputs)
        provider_artifacts_ch = IDR_PROVIDER.out.artifacts
        provider_reports_ch = IDR_PROVIDER.out.reports
        provider_versions_ch = IDR_PROVIDER.out.versions
        provider_execution_ch = IDR_PROVIDER.out.execution_metadata
        provider_manifest_ch = IDR_PROVIDER.out.manifest
        provider_status_ch = IDR_PROVIDER.out.status
    } else {
        error "Unsupported Consensus/IDR strategy '${strategy}'"
    }

    aggregate_inputs = provider_manifest_ch
        .map { _meta, manifest -> manifest }
        .collect()
        .map { manifests -> tuple([id: 'chipseq.consensus.aggregate', strategy: strategy], manifests) }
    CONSENSUS_AGGREGATE(aggregate_inputs)

    emit:
    artifacts          = provider_artifacts_ch
    summary            = CONSENSUS_AGGREGATE.out.artifacts
    reports            = CONSENSUS_CONTEXT.out.reports.mix(provider_reports_ch).mix(CONSENSUS_AGGREGATE.out.reports)
    versions           = CONSENSUS_CONTEXT.out.versions.mix(provider_versions_ch).mix(CONSENSUS_AGGREGATE.out.versions)
    execution_metadata = provider_execution_ch.mix(CONSENSUS_AGGREGATE.out.execution_metadata)
    provider_manifests = provider_manifest_ch
    manifest           = CONSENSUS_AGGREGATE.out.manifest
    provider_status    = provider_status_ch
    status             = CONSENSUS_AGGREGATE.out.status
}
