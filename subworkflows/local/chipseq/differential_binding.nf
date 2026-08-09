include { DB_PREFLIGHT } from '../../../modules/local/db_preflight/main'
include { PEAK_COUNTING_PROVIDER } from './peak_counting'
include { DESEQ2_DB_MODEL } from '../../../modules/local/deseq2_db_model/main'
include { DESEQ2_DB_CONTRAST } from '../../../modules/local/deseq2_db_contrast/main'
include { DB_AGGREGATE } from '../../../modules/local/db_aggregate/main'

workflow DIFFERENTIAL_BINDING {
    take:
    consensus_artifacts
    consensus_manifests
    final_bams
    final_bam_manifests
    peak_plan
    db_spec

    main:
    consensus_dirs_ch = consensus_artifacts.map { _meta, directory -> directory }.collect()
    consensus_manifests_ch = consensus_manifests.map { _meta, manifest -> manifest }.collect()
    bams_ch = final_bams.map { _meta, bam, _bai -> bam }.collect()
    bais_ch = final_bams.map { _meta, _bam, bai -> bai }.collect()
    bam_manifests_ch = final_bam_manifests.map { _meta, manifest -> manifest }.collect()
    plan_ch = peak_plan.map { _meta, _validated, plan -> plan }
    spec_ch = db_spec

    preflight_inputs = consensus_dirs_ch
        .combine(consensus_manifests_ch)
        .combine(bams_ch)
        .combine(bais_ch)
        .combine(bam_manifests_ch)
        .combine(plan_ch)
        .combine(spec_ch)
        .map { consensus_dirs, consensus_manifests_list, bams, bais, bam_manifests, plan, spec ->
            tuple([id: 'chipseq.differential_binding.preflight'], consensus_dirs, consensus_manifests_list,
                  bams, bais, bam_manifests, plan, spec)
        }
    DB_PREFLIGHT(preflight_inputs)

    analysis_plans = DB_PREFLIGHT.out.artifacts.flatMap { parent_meta, requests_dir, peaks_dir, samples_dir, count_specs_dir, model_specs_dir, contrast_specs_dir, spec ->
        requests_dir.toFile().listFiles().findAll { request_file -> request_file.name.endsWith('.json') }.sort { request_file -> request_file.name }.collect { request_file ->
            def request = new groovy.json.JsonSlurper().parse(request_file)
            def meta = parent_meta + [id: request.analysis_id, analysis_id: request.analysis_id, provider: 'featurecounts']
            tuple(request.analysis_id, meta, file("${peaks_dir}/${request.peak_bed}"),
                  file("${samples_dir}/${request.sample_table}"), file("${count_specs_dir}/${request.count_spec}"),
                  file("${model_specs_dir}/${request.model_spec}"), file(contrast_specs_dir), spec)
        }
    }

    count_requests = analysis_plans
        .combine(bams_ch)
        .combine(bais_ch)
        .combine(bam_manifests_ch)
        .map { _analysis_id, meta, peak_bed, _sample_table, count_spec, _model_spec, _contrast_specs_dir, _spec, bams, bais, manifests ->
            tuple(meta, peak_bed, bams, bais, manifests, count_spec)
        }
    PEAK_COUNTING_PROVIDER(count_requests)

    model_plans = analysis_plans.map { analysis_id, meta, peak_bed, sample_table, count_spec, model_spec, _contrast_specs_dir, _spec ->
        tuple(analysis_id, meta + [id: "${analysis_id}.deseq2", model_id: "${analysis_id}.deseq2", provider: 'deseq2'],
              peak_bed, sample_table, count_spec, model_spec)
    }
    count_outputs = PEAK_COUNTING_PROVIDER.out.artifacts
        .map { meta, counts_dir, count_spec -> tuple(meta.analysis_id, counts_dir, count_spec) }
        .join(PEAK_COUNTING_PROVIDER.out.manifest.map { meta, manifest -> tuple(meta.analysis_id, manifest) })
        .join(model_plans)
        .map { _analysis_id, counts_dir, count_spec_from_provider, count_manifest, model_meta, peak_bed, sample_table, _count_spec, model_spec ->
            tuple(model_meta, counts_dir, count_spec_from_provider, sample_table, model_spec, peak_bed, count_manifest)
        }
    DESEQ2_DB_MODEL(count_outputs)

    contrast_plans = analysis_plans.flatMap { analysis_id, _meta, _peak_bed, _sample_table, _count_spec, _model_spec, contrast_specs_dir, _spec ->
        contrast_specs_dir.toFile().listFiles()
            .findAll { contrast_file -> contrast_file.name.startsWith("${analysis_id}--") && contrast_file.name.endsWith('.json') }
            .sort { contrast_file -> contrast_file.name }
            .collect { contrast_file ->
                def contrast = new groovy.json.JsonSlurper().parse(contrast_file)
                def meta = [id: "${analysis_id}.${contrast.id}", analysis_id: analysis_id, model_id: contrast.model_id,
                            contrast_id: contrast.id, provider: 'deseq2']
                tuple(contrast.model_id, meta, file(contrast_file))
            }
    }
    model_outputs = DESEQ2_DB_MODEL.out.artifacts.map { meta, model_dir, model_spec, peak_bed ->
        tuple(meta.model_id, model_dir, model_spec, peak_bed)
    }
    contrast_inputs = model_outputs
        .join(contrast_plans)
        .map { _model_id, model_dir, model_spec, peak_bed, contrast_meta, contrast_spec ->
            tuple(contrast_meta, model_dir, model_spec, contrast_spec, peak_bed)
        }
    DESEQ2_DB_CONTRAST(contrast_inputs)

    aggregate_inputs = PEAK_COUNTING_PROVIDER.out.artifacts.map { _meta, directory, _spec -> directory }.collect()
        .combine(DESEQ2_DB_MODEL.out.artifacts.map { _meta, directory, _spec, _bed -> directory }.collect())
        .combine(DESEQ2_DB_CONTRAST.out.artifacts.map { _meta, directory -> directory }.collect())
        .combine(spec_ch)
        .map { count_dirs, model_dirs, contrast_dirs, spec ->
            tuple([id: 'chipseq.differential_binding'], count_dirs, model_dirs, contrast_dirs, spec)
        }
    DB_AGGREGATE(aggregate_inputs)

    emit:
    artifacts          = DB_AGGREGATE.out.artifacts
    results            = DB_AGGREGATE.out.results
    reports            = DB_PREFLIGHT.out.reports.mix(PEAK_COUNTING_PROVIDER.out.reports).mix(DESEQ2_DB_MODEL.out.reports).mix(DESEQ2_DB_CONTRAST.out.reports).mix(DB_AGGREGATE.out.reports)
    versions           = DB_PREFLIGHT.out.versions.mix(PEAK_COUNTING_PROVIDER.out.versions).mix(DESEQ2_DB_MODEL.out.versions).mix(DESEQ2_DB_CONTRAST.out.versions).mix(DB_AGGREGATE.out.versions)
    execution_metadata = PEAK_COUNTING_PROVIDER.out.execution_metadata.mix(DESEQ2_DB_MODEL.out.execution_metadata).mix(DESEQ2_DB_CONTRAST.out.execution_metadata).mix(DB_AGGREGATE.out.execution_metadata)
    manifest           = DB_AGGREGATE.out.manifest
    status             = DB_AGGREGATE.out.status
}
