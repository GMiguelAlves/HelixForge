include { RNASEQ_CONTEXT }   from '../../../modules/local/rnaseq_context/main'
include { RNASEQ_METADATA }  from '../../../modules/local/rnaseq_metadata/main'
include { REFERENCE_BUNDLE } from '../../../modules/local/reference_bundle/main'

workflow RNASEQ_NATIVE_FOUNDATION {
    take:
    config_file
    pipeline_root
    _seed

    main:
    context_meta = channel.value([id: 'rnaseq.context'])
    RNASEQ_CONTEXT(config_file, pipeline_root, context_meta)
    RNASEQ_METADATA(RNASEQ_CONTEXT.out.artifacts)

    if (params.rnaseq_run_mode.toString().toLowerCase() == 'qc') {
        foundation_reference_status = channel.value('none')
        foundation_annotation = channel.empty()
        foundation_reference_manifest = channel.empty()
        foundation_reference_logs = channel.empty()
    } else {
        reference_inputs = RNASEQ_METADATA.out.references
            .map { _meta, plan -> plan }
            .splitCsv(header: true, sep: '\t')
            .map { row ->
                def reference_id = row.reference_id.replaceAll(/[^A-Za-z0-9_.-]/, '_')
                def reference_meta = [id: reference_id, organism: row.organism]
                def genome = row.genome ? file(row.genome, checkIfExists: true) : []
                tuple(
                    reference_meta,
                    file(row.transcriptome, checkIfExists: true),
                    file(row.annotation, checkIfExists: true),
                    genome
                )
            }
        REFERENCE_BUNDLE(reference_inputs)
        foundation_reference_status = REFERENCE_BUNDLE.out.status.map { _meta, status -> status }
        foundation_annotation = REFERENCE_BUNDLE.out.artifacts.map { _meta, _transcriptome, annotation, _manifest -> annotation }
        foundation_reference_manifest = REFERENCE_BUNDLE.out.artifacts.map { _meta, _transcriptome, _annotation, manifest -> manifest }
        foundation_reference_logs = REFERENCE_BUNDLE.out.reports.map { meta, _validation, log -> tuple(meta, log) }
    }

    emit:
    qc_plans = RNASEQ_METADATA.out.artifacts.map { _meta, plans -> plans }.flatten()
    metadata_status = RNASEQ_METADATA.out.status.map { _meta, status -> status }
    reference_status = foundation_reference_status
    metadata = RNASEQ_METADATA.out.reports.map { _meta, normalized, _validation, _log -> normalized }
    annotation = foundation_annotation
    reference_manifest = foundation_reference_manifest
    logs = RNASEQ_CONTEXT.out.reports
        .mix(RNASEQ_METADATA.out.reports.map { meta, _normalized, _validation, log -> tuple(meta, log) })
        .mix(foundation_reference_logs)
}
