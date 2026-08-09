include { BAM_SELECT }     from '../../../modules/local/bam_select/main'
include { BAM_DUPLICATES } from '../../../modules/local/bam_duplicates/main'
include { BAM_BLACKLIST }  from '../../../modules/local/bam_blacklist/main'
include { BAM_INDEX_QC }   from '../../../modules/local/bam_index_qc/main'

workflow CHIPSEQ_BAM_PROCESSING {
    take:
    processing_inputs

    main:
    select_inputs = processing_inputs.map {
        meta, bam, bai, reference, _blacklist, select_params, _duplicate_params, _blacklist_params, _qc_params ->
        tuple(meta, bam, bai, reference, select_params)
    }
    BAM_SELECT(select_inputs)

    duplicate_context = processing_inputs.map {
        meta, _bam, _bai, reference, blacklist, _select_params, duplicate_params, blacklist_params, qc_params ->
        tuple(meta.id, reference, blacklist, duplicate_params, blacklist_params, qc_params)
    }
    duplicate_inputs = BAM_SELECT.out.artifacts
        .map { meta, selected_bam -> tuple(meta.id, meta, selected_bam) }
        .join(duplicate_context)
        .map { _id, meta, selected_bam, _reference, _blacklist, duplicate_params, _blacklist_params, _qc_params ->
            tuple(meta, selected_bam, duplicate_params)
        }
    BAM_DUPLICATES(duplicate_inputs)

    select_contigs = BAM_SELECT.out.reports.map { meta, reports ->
        tuple(meta.id, reports.resolve('bam_contigs.tsv'))
    }
    blacklist_context = processing_inputs.map {
        meta, _bam, _bai, _reference, blacklist, _select_params, _duplicate_params, blacklist_params, _qc_params ->
        tuple(meta.id, blacklist, blacklist_params)
    }
    blacklist_inputs = BAM_DUPLICATES.out.artifacts
        .map { meta, duplicate_bam -> tuple(meta.id, meta, duplicate_bam) }
        .join(select_contigs)
        .join(blacklist_context)
        .map { _id, meta, duplicate_bam, bam_contigs, blacklist, blacklist_params ->
            tuple(meta, duplicate_bam, bam_contigs, blacklist, blacklist_params)
        }
    BAM_BLACKLIST(blacklist_inputs)

    final_context = processing_inputs.map {
        meta, _bam, _bai, reference, _blacklist, _select_params, _duplicate_params, _blacklist_params, qc_params ->
        tuple(meta.id, reference, qc_params)
    }
    final_inputs = BAM_BLACKLIST.out.artifacts
        .map { meta, blacklist_bam -> tuple(meta.id, meta, blacklist_bam) }
        .join(final_context)
        .map { _id, meta, blacklist_bam, reference, qc_params ->
            tuple(meta, blacklist_bam, reference, qc_params)
        }
    BAM_INDEX_QC(final_inputs)

    emit:
    artifacts          = BAM_INDEX_QC.out.artifacts
    reports            = BAM_SELECT.out.reports
        .mix(BAM_DUPLICATES.out.reports)
        .mix(BAM_BLACKLIST.out.reports)
        .mix(BAM_INDEX_QC.out.reports)
    versions           = BAM_SELECT.out.versions
        .mix(BAM_DUPLICATES.out.versions)
        .mix(BAM_BLACKLIST.out.versions)
        .mix(BAM_INDEX_QC.out.versions)
    execution_metadata = BAM_SELECT.out.execution_metadata
        .mix(BAM_DUPLICATES.out.execution_metadata)
        .mix(BAM_BLACKLIST.out.execution_metadata)
        .mix(BAM_INDEX_QC.out.execution_metadata)
    manifests          = BAM_SELECT.out.manifest
        .mix(BAM_DUPLICATES.out.manifest)
        .mix(BAM_BLACKLIST.out.manifest)
        .mix(BAM_INDEX_QC.out.manifest)
    final_manifest     = BAM_INDEX_QC.out.manifest
    status             = BAM_INDEX_QC.out.status
}

