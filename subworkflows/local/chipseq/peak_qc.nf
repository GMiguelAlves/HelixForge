include { PEAK_QC_CONTEXT }   from '../../../modules/local/peak_qc_context/main'
include { FRIP }              from '../../../modules/local/frip/main'
include { PEAK_STATISTICS }   from '../../../modules/local/peak_statistics/main'
include { PEAK_QC_AGGREGATE } from '../../../modules/local/peak_qc_aggregate/main'


workflow PEAK_QC {
    take:
    final_bams
    final_bam_manifests
    peak_artifacts
    peak_manifests
    peak_plan
    qc_spec_base64

    main:
    bam_records = final_bams
        .map { meta, bam, bai -> tuple(meta.id, meta, bam, bai) }
        .join(final_bam_manifests.map { _meta, manifest -> tuple(_meta.id, manifest) })

    peak_records = peak_artifacts
        .map { meta, result_dir -> tuple(meta.id, meta, result_dir) }
        .join(peak_manifests.map { meta, manifest -> tuple(meta.id, manifest) })
        .map { _peak_id, meta, result_dir, manifest ->
            def document = new groovy.json.JsonSlurper().parse(manifest.toFile())
            def extension = document.peak_type == 'narrow' ? 'narrowPeak' : 'broadPeak'
            tuple(document.record_id, meta, result_dir.resolve("peaks.${extension}"), manifest, document)
        }

    plan_by_record = peak_plan
        .map { _meta, _validated_plan, plan -> plan }
        .splitCsv(header: true, sep: '\t')
        .map { row -> tuple(row.record_id, row) }

    context_inputs = peak_records
        .join(bam_records)
        .join(plan_by_record)
        .map { record_id, _peak_meta, peaks, peak_manifest, peak_document,
               bam_meta, bam, bai, bam_manifest, row ->
            if (peak_document.record_id != record_id || bam_meta.id != record_id) {
                error "Unsafe Peak QC association for record ${record_id}"
            }
            def context_meta = bam_meta + [
                id                   : peak_document.id,
                peak_id              : peak_document.id,
                record_id            : record_id,
                sample_id            : peak_document.sample_id,
                experiment_id        : peak_document.experiment_id,
                target               : peak_document.target,
                control_id           : peak_document.control_id ?: '',
                control_record_id    : peak_document.control_record_id ?: '',
                biological_replicate : peak_document.biological_replicate,
                technical_replicate  : peak_document.technical_replicate,
                peak_type            : peak_document.peak_type,
                caller               : peak_document.caller,
                caller_version       : peak_document.caller_version,
                reference            : row.genome_id,
                peak_qc_target_dir   : "${params.outdir}/chipseq/peak_qc/${peak_document.id}",
            ]
            def selected_blacklist = row.blacklist_bed && !(row.blacklist_bed.toLowerCase() in ['none', 'false']) \
                ? file(row.blacklist_bed, checkIfExists: true) : []
            tuple(
                context_meta, bam, bai, bam_manifest, peaks, peak_manifest,
                file(row.genome_fasta, checkIfExists: true), selected_blacklist, qc_spec_base64
            )
        }

    PEAK_QC_CONTEXT(context_inputs)

    source_by_peak = context_inputs.map {
        meta, bam, bai, _bam_manifest, peaks, _peak_manifest, _reference, _blacklist, _spec ->
        tuple(meta.peak_id, meta, bam, bai, peaks)
    }
    validated = PEAK_QC_CONTEXT.out.artifacts
        .map { meta, request -> tuple(meta.peak_id, request) }
        .join(source_by_peak)

    frip_inputs = validated.map { _peak_id, request, meta, bam, bai, peaks -> tuple(meta, bam, bai, peaks, request) }
    statistics_inputs = validated.map { _peak_id, request, meta, _bam, _bai, peaks -> tuple(meta, peaks, request) }
    FRIP(frip_inputs)
    PEAK_STATISTICS(statistics_inputs)

    replicate_artifacts = FRIP.out.artifacts
        .map { meta, frip_json, frip_tsv -> tuple(meta.peak_id, meta, frip_json, frip_tsv) }
        .join(PEAK_STATISTICS.out.artifacts.map { meta, statistics_json -> tuple(meta.peak_id, statistics_json) })
        .map { _peak_id, meta, frip_json, frip_tsv, statistics_json -> tuple(meta, frip_json, frip_tsv, statistics_json) }

    frip_manifest_list = FRIP.out.manifest.map { _meta, manifest -> manifest }.collect()
    statistics_manifest_list = PEAK_STATISTICS.out.manifest.map { _meta, manifest -> manifest }.collect()
    aggregate_inputs = frip_manifest_list
        .map { manifests -> tuple('peak_qc', manifests) }
        .join(statistics_manifest_list.map { manifests -> tuple('peak_qc', manifests) })
        .map { _key, frip_files, statistics_files ->
            tuple([id: 'chipseq.peak_qc.aggregate'], frip_files, statistics_files)
        }
    PEAK_QC_AGGREGATE(aggregate_inputs)

    emit:
    artifacts          = replicate_artifacts
    summary            = PEAK_QC_AGGREGATE.out.artifacts
    reports            = PEAK_QC_CONTEXT.out.reports
        .mix(FRIP.out.reports)
        .mix(PEAK_STATISTICS.out.reports)
        .mix(PEAK_QC_AGGREGATE.out.reports)
    versions           = PEAK_QC_CONTEXT.out.versions
        .mix(FRIP.out.versions)
        .mix(PEAK_STATISTICS.out.versions)
        .mix(PEAK_QC_AGGREGATE.out.versions)
    execution_metadata = FRIP.out.execution_metadata
        .mix(PEAK_STATISTICS.out.execution_metadata)
        .mix(PEAK_QC_AGGREGATE.out.execution_metadata)
    replicate_manifests = FRIP.out.manifest.mix(PEAK_STATISTICS.out.manifest)
    manifest           = PEAK_QC_AGGREGATE.out.manifest
    status             = PEAK_QC_AGGREGATE.out.status
}
