include { MACS3_CALLPEAK }        from '../../../modules/local/macs3_callpeak/main'
include { PEAK_CALLING_AGGREGATE } from '../../../modules/local/peak_calling_aggregate/main'


def encode_peak_request(row, treatment_meta, reference_sha256, control_meta = null) {
    def request = [
        schema_version        : '1.0',
        peak_id               : row.peak_id,
        sample_id             : row.sample_id,
        record_id             : row.record_id,
        experiment_id         : "${row.dataset}.${row.target}",
        dataset               : row.dataset,
        target                : row.target,
        condition             : row.condition,
        biological_replicate  : row.biological_replicate,
        technical_replicate   : row.technical_replicate,
        layout                : row.layout,
        paired_end            : row.layout == 'paired',
        genome_id             : row.genome_id,
        organism              : row.organism,
        reference             : row.genome_id,
        reference_sha256      : reference_sha256,
        blacklist             : row.blacklist_bed ?: null,
        caller                : row.caller,
        caller_version        : row.caller_version,
        peak_type             : row.peak_type,
        effective_genome_size : row.effective_genome_size,
        cutoff_type           : row.cutoff_type,
        cutoff                : row.cutoff as Double,
        q_value               : row.q_value ? row.q_value as Double : null,
        p_value               : row.p_value ? row.p_value as Double : null,
        format                : row.format,
        paired_end_handling   : row.paired_end_handling,
        duplicate_policy      : row.duplicate_policy,
        additional_args       : row.additional_args,
        control_id            : row.control_id ?: null,
        control_record_id     : row.control_record_id ?: null,
        treatment_bam         : treatment_meta.id,
        control_bam           : control_meta?.id,
    ]
    groovy.json.JsonOutput.toJson(request).getBytes('UTF-8').encodeBase64().toString()
}


workflow PEAK_CALLING {
    take:
    final_bams
    final_bam_manifests
    peak_plan

    main:
    peak_rows = peak_plan
        .map { _meta, _validated_plan, plan -> plan }
        .splitCsv(header: true, sep: '\t')

    manifests_by_record = final_bam_manifests.map { meta, manifest ->
        def document = new groovy.json.JsonSlurper().parse(manifest.toFile())
        tuple(meta.id, manifest, document.reference_sha256 ?: '')
    }
    bam_records = final_bams
        .map { meta, bam, bai -> tuple(meta.id, meta, bam, bai) }
        .join(manifests_by_record)

    treatments = peak_rows
        .map { row -> tuple(row.record_id, row) }
        .combine(bam_records, by: 0)

    requests_without_control = treatments
        .filter { _id, row, _meta, _bam, _bai, _manifest, _reference_sha -> !row.control_record_id }
        .map { _id, row, treatment_meta, treatment_bam, treatment_bai, _manifest, reference_sha ->
            def meta = treatment_meta + [
                id                 : row.peak_id,
                peak_id            : row.peak_id,
                experiment_id      : "${row.dataset}.${row.target}",
                caller             : row.caller,
                caller_version     : row.caller_version,
                peak_type          : row.peak_type,
                control_record_id  : '',
                peak_target_dir    : row.peak_target_dir,
            ]
            tuple(meta, treatment_bam, treatment_bai, [], [], encode_peak_request(row, treatment_meta, reference_sha))
        }

    control_requests = treatments
        .filter { _id, row, _meta, _bam, _bai, _manifest, _reference_sha -> row.control_record_id }
        .map { _id, row, treatment_meta, treatment_bam, treatment_bai, treatment_manifest, reference_sha ->
            tuple(row.control_record_id, row, treatment_meta, treatment_bam, treatment_bai, treatment_manifest, reference_sha)
        }
        .combine(bam_records, by: 0)
        .map { _control_id, row, treatment_meta, treatment_bam, treatment_bai, _treatment_manifest, reference_sha,
               control_meta, control_bam, control_bai, _control_manifest, _control_reference_sha ->
            def meta = treatment_meta + [
                id                 : row.peak_id,
                peak_id            : row.peak_id,
                experiment_id      : "${row.dataset}.${row.target}",
                caller             : row.caller,
                caller_version     : row.caller_version,
                peak_type          : row.peak_type,
                control_record_id  : control_meta.id,
                peak_target_dir    : row.peak_target_dir,
            ]
            tuple(
                meta, treatment_bam, treatment_bai, [control_bam], [control_bai],
                encode_peak_request(row, treatment_meta, reference_sha, control_meta)
            )
        }

    provider_requests = requests_without_control.mix(control_requests)
    MACS3_CALLPEAK(provider_requests)

    provider_manifests = MACS3_CALLPEAK.out.manifest.map { meta, manifest -> tuple(meta.id, manifest) }
    aggregate_inputs = MACS3_CALLPEAK.out.artifacts
        .map { meta, peaks, provider_dir, request -> tuple(meta.id, meta, peaks, provider_dir, request) }
        .join(provider_manifests)
        .map { _id, meta, peaks, provider_dir, request, provider_manifest ->
            tuple(meta, peaks, provider_dir, provider_manifest, request)
        }
    PEAK_CALLING_AGGREGATE(aggregate_inputs)

    emit:
    artifacts          = PEAK_CALLING_AGGREGATE.out.artifacts
    reports            = MACS3_CALLPEAK.out.reports.mix(PEAK_CALLING_AGGREGATE.out.reports)
    versions           = MACS3_CALLPEAK.out.versions.mix(PEAK_CALLING_AGGREGATE.out.versions)
    execution_metadata = MACS3_CALLPEAK.out.execution_metadata.mix(PEAK_CALLING_AGGREGATE.out.execution_metadata)
    manifests          = PEAK_CALLING_AGGREGATE.out.manifest
    provider_manifests = MACS3_CALLPEAK.out.manifest
    status             = PEAK_CALLING_AGGREGATE.out.status
}
