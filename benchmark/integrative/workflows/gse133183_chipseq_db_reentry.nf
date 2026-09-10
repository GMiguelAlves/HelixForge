nextflow.enable.dsl = 2

include { DESEQ2_DB_MODEL } from '../../../modules/local/deseq2_db_model/main'
include { DESEQ2_DB_CONTRAST } from '../../../modules/local/deseq2_db_contrast/main'
include { DB_AGGREGATE } from '../../../modules/local/db_aggregate/main'

workflow {
    required = [
        counts_dir      : params.counts_dir,
        count_spec      : params.count_spec,
        sample_table    : params.sample_table,
        model_spec      : params.model_spec,
        contrast_spec   : params.contrast_spec,
        peak_bed        : params.peak_bed,
        count_manifest  : params.count_manifest,
        db_spec         : params.db_spec,
    ]
    missing = required.findAll { _key, value -> value == null || value.toString().trim() == '' }.keySet()
    if (missing) {
        error "ChIP-seq DB re-entry requires: ${missing.sort().join(', ')}"
    }

    counts_dir = file(params.counts_dir, checkIfExists: true)
    count_spec = file(params.count_spec, checkIfExists: true)
    sample_table = file(params.sample_table, checkIfExists: true)
    model_spec = file(params.model_spec, checkIfExists: true)
    contrast_spec = file(params.contrast_spec, checkIfExists: true)
    peak_bed = file(params.peak_bed, checkIfExists: true)
    count_manifest = file(params.count_manifest, checkIfExists: true)
    db_spec = file(params.db_spec, checkIfExists: true)

    model_document = new groovy.json.JsonSlurper().parse(model_spec.toFile())
    contrast_document = new groovy.json.JsonSlurper().parse(contrast_spec.toFile())
    analysis_id = model_document.analysis_id.toString()
    model_id = model_document.model_id.toString()
    contrast_id = contrast_document.id.toString()

    model_meta = [id: model_id, analysis_id: analysis_id, model_id: model_id, provider: 'deseq2']
    DESEQ2_DB_MODEL(channel.value(tuple(model_meta, counts_dir, count_spec, sample_table,
        model_spec, peak_bed, count_manifest)))

    contrast_inputs = DESEQ2_DB_MODEL.out.artifacts.map { _meta, model_dir, resolved_model_spec, resolved_peak_bed ->
        def meta = [
            id: "${analysis_id}.${contrast_id}", analysis_id: analysis_id,
            model_id: model_id, contrast_id: contrast_id, provider: 'deseq2'
        ]
        tuple(meta, model_dir, resolved_model_spec, contrast_spec, resolved_peak_bed)
    }
    DESEQ2_DB_CONTRAST(contrast_inputs)

    aggregate_inputs = DESEQ2_DB_MODEL.out.artifacts
        .combine(DESEQ2_DB_CONTRAST.out.artifacts)
        .map { _model_meta, model_dir, _model_spec, _peak_bed, _contrast_meta, contrast_dir ->
            tuple([id: 'chipseq.differential_binding.reentry'], [counts_dir], [model_dir], [contrast_dir], db_spec)
        }
    DB_AGGREGATE(aggregate_inputs)
}
