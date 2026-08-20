include { RNASEQ_NATIVE_FOUNDATION }        from '../subworkflows/local/rnaseq/native_foundation'
include { RNASEQ_QC }                       from '../subworkflows/local/rnaseq/qc'
include { RNASEQ_ALIGNMENT_QUANTIFICATION } from '../subworkflows/local/rnaseq/alignment_quantification'
include { RNASEQ_DIFFERENTIAL_EXPRESSION }  from '../subworkflows/local/rnaseq/differential_expression'
include { RUN_MANIFEST }                    from '../modules/local/run_manifest/main'

workflow RNASEQ {
    take:
    seed

    main:
    config_file = file(params.rnaseq_config, checkIfExists: true)
    pipeline_root = "${projectDir}/pipelines/rnaseq"
    run_mode = params.rnaseq_run_mode.toString().toLowerCase()
    if (!(run_mode in ['qc', 'alignment', 'quant', 'quantification', 'import', 'de', 'differential_expression', 'report', 'full'])) {
        error "Invalid rnaseq_run_mode '${params.rnaseq_run_mode}'. Use qc, alignment, quantification, import, de, report, or full."
    }

    terminal_manifest = channel.empty()
    RNASEQ_NATIVE_FOUNDATION(config_file, pipeline_root, seed)
    RNASEQ_QC(RNASEQ_NATIVE_FOUNDATION.out.qc_plans)
    if (run_mode == 'qc') {
        completed_status = RNASEQ_QC.out.status
        analysis_logs = channel.empty()
        downstream_logs = channel.empty()
    } else {
        RNASEQ_ALIGNMENT_QUANTIFICATION(
            config_file,
            pipeline_root,
            RNASEQ_NATIVE_FOUNDATION.out.reference_status,
            RNASEQ_QC.out.status,
            RNASEQ_QC.out.plans,
            RNASEQ_NATIVE_FOUNDATION.out.metadata,
            RNASEQ_NATIVE_FOUNDATION.out.annotation
        )
        analysis_logs = RNASEQ_ALIGNMENT_QUANTIFICATION.out.logs
        if (run_mode in ['alignment', 'quant', 'quantification', 'import']) {
            completed_status = RNASEQ_ALIGNMENT_QUANTIFICATION.out.status
            downstream_logs = channel.empty()
        } else {
            RNASEQ_DIFFERENTIAL_EXPRESSION(
                config_file,
                pipeline_root,
                RNASEQ_ALIGNMENT_QUANTIFICATION.out.status,
                RNASEQ_ALIGNMENT_QUANTIFICATION.out.import_manifest,
                RNASEQ_ALIGNMENT_QUANTIFICATION.out.imported_counts,
                RNASEQ_ALIGNMENT_QUANTIFICATION.out.imported_abundance,
                RNASEQ_ALIGNMENT_QUANTIFICATION.out.imported_metadata,
                RNASEQ_NATIVE_FOUNDATION.out.annotation
            )
            completed_status = RNASEQ_DIFFERENTIAL_EXPRESSION.out.status
            downstream_logs = RNASEQ_DIFFERENTIAL_EXPRESSION.out.logs

            if (run_mode == 'full') {
                quant_records = RNASEQ_ALIGNMENT_QUANTIFICATION.out.quantification.map { meta, artifact ->
                    def descriptor = [
                        artifact_id: "${meta.id}.transcript_abundance", artifact_type: 'transcript_abundance',
                        assay: 'rnaseq', format: 'salmon_quant_sf', entity_level: 'transcript',
                        contrast_id: null, sample_ids: [meta.sample_id], condition: null, stage: null,
                        mark_or_factor: null, peak_type: null, role: 'quantification',
                        producer_manifest_id: meta.id, producer_process: 'SALMON_QUANT',
                        location: [kind: 'producer_relative', path: artifact.name, base_path: null, producer_manifest_id: meta.id],
                        source: [type: 'helixforge', name: 'Salmon', version: '1.10.3'], metadata: [dataset: meta.dataset]
                    ]
                    tuple(descriptor, artifact)
                }
                count_records = RNASEQ_ALIGNMENT_QUANTIFICATION.out.imported_counts.map { meta, artifact ->
                    tuple([
                        artifact_id: "${meta.id}.gene_counts", artifact_type: 'gene_counts', assay: 'rnaseq',
                        format: 'tsv', entity_level: 'gene', contrast_id: null, sample_ids: [], condition: null,
                        stage: null, mark_or_factor: null, peak_type: null, role: 'counts',
                        producer_manifest_id: meta.id, producer_process: meta.provider == 'salmon' ? 'TXIMPORT' : 'STAR_IMPORT',
                        location: [kind: 'producer_relative', path: artifact.name, base_path: null, producer_manifest_id: meta.id],
                        source: [type: 'helixforge', name: meta.provider, version: null], metadata: [:]
                    ], artifact)
                }
                abundance_records = RNASEQ_ALIGNMENT_QUANTIFICATION.out.imported_abundance.map { meta, artifact ->
                    tuple([
                        artifact_id: "${meta.id}.gene_abundance", artifact_type: 'gene_abundance', assay: 'rnaseq',
                        format: 'tsv', entity_level: 'gene', contrast_id: null, sample_ids: [], condition: null,
                        stage: null, mark_or_factor: null, peak_type: null, role: 'abundance',
                        producer_manifest_id: meta.id, producer_process: meta.provider == 'salmon' ? 'TXIMPORT' : 'STAR_IMPORT',
                        location: [kind: 'producer_relative', path: artifact.name, base_path: null, producer_manifest_id: meta.id],
                        source: [type: 'helixforge', name: meta.provider, version: null], metadata: [:]
                    ], artifact)
                }
                de_summary_records = RNASEQ_DIFFERENTIAL_EXPRESSION.out.common_results.map { meta, artifact ->
                    tuple([
                        artifact_id: "${meta.analysis_id}.differential_expression_summary", artifact_type: 'differential_expression_summary', assay: 'rnaseq',
                        format: 'tsv', entity_level: 'gene', contrast_id: null, sample_ids: [], condition: null,
                        stage: null, mark_or_factor: null, peak_type: null, role: 'combined_results',
                        producer_manifest_id: meta.analysis_id, producer_process: 'DE_AGGREGATE',
                        location: [kind: 'producer_relative', path: artifact.name, base_path: null, producer_manifest_id: meta.analysis_id],
                        source: [type: 'helixforge', name: 'DESeq2', version: null], metadata: [:]
                    ], artifact)
                }
                de_records = RNASEQ_DIFFERENTIAL_EXPRESSION.out.contrast_results.map { meta, artifact ->
                    tuple([
                        artifact_id: "${meta.id}.differential_expression", artifact_type: 'differential_expression', assay: 'rnaseq',
                        format: 'tsv', entity_level: 'gene', contrast_id: meta.contrast_id, sample_ids: [], condition: null,
                        stage: null, mark_or_factor: null, peak_type: null, role: 'contrast_results',
                        producer_manifest_id: meta.id, producer_process: 'DESEQ2_CONTRAST',
                        location: [kind: 'producer_relative', path: artifact.name, base_path: null, producer_manifest_id: meta.id],
                        source: [type: 'helixforge', name: 'DESeq2', version: null], metadata: [model_id: meta.model_id]
                    ], artifact)
                }
                normalized_records = RNASEQ_DIFFERENTIAL_EXPRESSION.out.normalized_counts.map { meta, artifact ->
                    tuple([
                        artifact_id: "${meta.id}.normalized_counts", artifact_type: 'normalized_counts', assay: 'rnaseq',
                        format: 'tsv', entity_level: 'gene', contrast_id: null, sample_ids: [], condition: null,
                        stage: null, mark_or_factor: null, peak_type: null, role: 'exploratory_expression',
                        producer_manifest_id: meta.id, producer_process: 'DESEQ2_MODEL',
                        location: [kind: 'producer_relative', path: artifact.name, base_path: null, producer_manifest_id: meta.id],
                        source: [type: 'helixforge', name: 'DESeq2', version: null], metadata: [model_id: meta.model_id]
                    ], artifact)
                }
                report_records = RNASEQ_DIFFERENTIAL_EXPRESSION.out.report_artifacts.map { meta, artifact ->
                    tuple([
                        artifact_id: "${meta.id}.report", artifact_type: 'rnaseq_report', assay: 'rnaseq',
                        format: 'directory', entity_level: 'report', contrast_id: null, sample_ids: [], condition: null,
                        stage: null, mark_or_factor: null, peak_type: null, role: 'report',
                        producer_manifest_id: meta.id, producer_process: 'RNASEQ_GENE_REPORT',
                        location: [kind: 'producer_relative', path: '.', base_path: null, producer_manifest_id: meta.id],
                        source: [type: 'helixforge', name: meta.provider, version: '1.0'], metadata: [:]
                    ], artifact)
                }
                terminal_records = quant_records
                    .mix(count_records)
                    .mix(abundance_records)
                    .mix(de_records)
                    .mix(de_summary_records)
                    .mix(normalized_records)
                    .mix(report_records)
                terminal_record_bundle = terminal_records.toList().map { records ->
                    def ordered = records.sort { left, right -> left[0]['artifact_id'] <=> right[0]['artifact_id'] }
                    tuple(
                        'terminal_manifest',
                        ordered.collect { value -> value[1] },
                        groovy.json.JsonOutput.toJson(ordered.collect { value -> value[0] }).bytes.encodeBase64().toString()
                    )
                }
                terminal_source_manifests = RNASEQ_ALIGNMENT_QUANTIFICATION.out.quantification_manifest
                    .map { _meta, manifest -> manifest }
                    .mix(RNASEQ_ALIGNMENT_QUANTIFICATION.out.import_manifest.map { _meta, manifest -> manifest })
                    .mix(RNASEQ_DIFFERENTIAL_EXPRESSION.out.manifest.map { _meta, manifest -> manifest })
                    .mix(RNASEQ_DIFFERENTIAL_EXPRESSION.out.model_manifest.map { _meta, manifest -> manifest })
                    .mix(RNASEQ_DIFFERENTIAL_EXPRESSION.out.contrast_manifest.map { _meta, manifest -> manifest })
                    .mix(RNASEQ_DIFFERENTIAL_EXPRESSION.out.report_manifest.map { _meta, manifest -> manifest })
                    .toList()
                    .map { manifests -> tuple('terminal_manifest', manifests) }
                terminal_metadata = RNASEQ_NATIVE_FOUNDATION.out.metadata.map { metadata -> tuple('terminal_manifest', metadata) }
                terminal_reference = RNASEQ_NATIVE_FOUNDATION.out.reference_manifest.map { manifest -> tuple('terminal_manifest', manifest) }
                terminal_method = RNASEQ_ALIGNMENT_QUANTIFICATION.out.quantification_method.map { method -> tuple('terminal_manifest', method) }
                terminal_inputs = terminal_record_bundle
                    .join(terminal_source_manifests)
                    .join(terminal_metadata)
                    .join(terminal_reference)
                    .join(terminal_method)
                    .map { _key, artifacts, descriptors, manifests, metadata, reference_manifest, quantification_method ->
                        def safe_run = workflow.runName.replaceAll(/[^A-Za-z0-9._-]+/, '_')
                        def manifest_meta = [id: "${safe_run}.rnaseq", assay: 'rnaseq']
                        def run = [
                            id: manifest_meta.id, run_id: workflow.sessionId.toString(), run_name: workflow.runName,
                            helixforge_version: workflow.manifest.version ?: 'unknown', git_commit: workflow.commitId ?: 'unknown',
                            nextflow_version: workflow.nextflow.version.toString(), profile: workflow.profile ?: '',
                            quantification_method: quantification_method.toString(), source: [type: 'helixforge', name: 'HelixForge', version: workflow.manifest.version ?: 'unknown']
                        ]
                        def run_base64 = groovy.json.JsonOutput.toJson(run).bytes.encodeBase64().toString()
                        tuple(manifest_meta, metadata, reference_manifest,
                            file("${projectDir}/schemas/integration", checkIfExists: true), manifests, artifacts,
                            file(params.rnaseq_de_spec, checkIfExists: true), run_base64, descriptors)
                    }
                RUN_MANIFEST(terminal_inputs)
                terminal_manifest = RUN_MANIFEST.out.artifacts
                downstream_logs = downstream_logs.mix(RUN_MANIFEST.out.reports)
            }
        }
    }

    emit:
    completed = completed_status
    terminal_manifest = terminal_manifest
    logs      = RNASEQ_NATIVE_FOUNDATION.out.logs
        .mix(RNASEQ_QC.out.logs)
        .mix(analysis_logs)
        .mix(downstream_logs)
}
