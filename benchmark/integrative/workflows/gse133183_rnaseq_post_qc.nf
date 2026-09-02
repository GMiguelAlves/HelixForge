nextflow.enable.dsl=2

include { RNASEQ_ALIGNMENT_QUANTIFICATION } from '../../../subworkflows/local/rnaseq/alignment_quantification'
include { RNASEQ_DIFFERENTIAL_EXPRESSION }  from '../../../subworkflows/local/rnaseq/differential_expression'
include { RUN_MANIFEST }                   from '../../../modules/local/run_manifest/main'

/*
 * Benchmark-only re-entry after a previously completed native QC boundary.
 *
 * This workflow deliberately does not include RNASEQ_QC. It consumes the
 * published QC plan, normalized metadata and reference manifest from the
 * audited GSE133183 run, then executes the unchanged production subworkflows.
 */
workflow GSE133183_RNASEQ_POST_QC {
    main:
    helixforge_root = file(params.helixforge_root, checkIfExists: true)
    config_file = file(params.rnaseq_config, checkIfExists: true)
    qc_plan = channel.of(file(params.precomputed_qc_plan, checkIfExists: true))
    metadata = channel.value(file(params.precomputed_metadata, checkIfExists: true))
    annotation = channel.value(file(params.precomputed_annotation, checkIfExists: true))
    reference_manifest = channel.value(file(params.precomputed_reference_manifest, checkIfExists: true))
    reference_status = channel.value('PRECOMPUTED_REFERENCE_VALIDATED')
    qc_status = channel.value('PRECOMPUTED_NATIVE_QC_VALIDATED')
    pipeline_root = "${helixforge_root}/pipelines/rnaseq"

    RNASEQ_ALIGNMENT_QUANTIFICATION(
        config_file,
        pipeline_root,
        reference_status,
        qc_status,
        qc_plan,
        metadata,
        annotation
    )
    RNASEQ_DIFFERENTIAL_EXPRESSION(
        config_file,
        pipeline_root,
        RNASEQ_ALIGNMENT_QUANTIFICATION.out.status,
        RNASEQ_ALIGNMENT_QUANTIFICATION.out.import_manifest,
        RNASEQ_ALIGNMENT_QUANTIFICATION.out.imported_counts,
        RNASEQ_ALIGNMENT_QUANTIFICATION.out.imported_abundance,
        RNASEQ_ALIGNMENT_QUANTIFICATION.out.imported_metadata,
        annotation
    )

    quant_records = RNASEQ_ALIGNMENT_QUANTIFICATION.out.quantification.map { meta, artifact ->
        tuple([
            artifact_id: "${meta.id}.transcript_abundance", artifact_type: 'transcript_abundance',
            assay: 'rnaseq', format: 'salmon_quant_sf', entity_level: 'transcript',
            contrast_id: null, sample_ids: [meta.sample_id], condition: null, stage: null,
            mark_or_factor: null, peak_type: null, role: 'quantification',
            producer_manifest_id: meta.id, producer_process: 'SALMON_QUANT',
            location: [kind: 'producer_relative', path: artifact.name, base_path: null, producer_manifest_id: meta.id],
            source: [type: 'helixforge', name: 'Salmon', version: '1.10.3'], metadata: [dataset: meta.dataset]
        ], artifact)
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
    terminal_metadata = metadata.map { value -> tuple('terminal_manifest', value) }
    terminal_reference = reference_manifest.map { value -> tuple('terminal_manifest', value) }
    terminal_method = RNASEQ_ALIGNMENT_QUANTIFICATION.out.quantification_method
        .map { method -> tuple('terminal_manifest', method) }
    terminal_inputs = terminal_record_bundle
        .join(terminal_source_manifests)
        .join(terminal_metadata)
        .join(terminal_reference)
        .join(terminal_method)
        .map { _key, artifacts, descriptors, manifests, metadata_file, reference_file, quantification_method ->
            def safe_run = workflow.runName.replaceAll(/[^A-Za-z0-9._-]+/, '_')
            def manifest_meta = [id: "${safe_run}.rnaseq", assay: 'rnaseq']
            def run = [
                id: manifest_meta.id, run_id: workflow.sessionId.toString(), run_name: workflow.runName,
                helixforge_version: workflow.manifest.version ?: 'unknown', git_commit: workflow.commitId ?: 'unknown',
                nextflow_version: workflow.nextflow.version.toString(), profile: workflow.profile ?: '',
                quantification_method: quantification_method.toString(),
                source: [type: 'helixforge', name: 'HelixForge', version: workflow.manifest.version ?: 'unknown'],
                parameters: [benchmark_reentry: [boundary: 'post_qc', reason: 'NFS task-cache persistence unavailable']]
            ]
            def run_base64 = groovy.json.JsonOutput.toJson(run).bytes.encodeBase64().toString()
            tuple(
                manifest_meta, metadata_file, reference_file,
                file("${helixforge_root}/schemas/integration", checkIfExists: true), manifests, artifacts,
                file(params.rnaseq_de_spec, checkIfExists: true), run_base64, descriptors
            )
        }
    RUN_MANIFEST(terminal_inputs)

    emit:
    completed = RNASEQ_DIFFERENTIAL_EXPRESSION.out.status
    terminal_manifest = RUN_MANIFEST.out.artifacts
    terminal_bundle = RUN_MANIFEST.out.bundle
    logs = RNASEQ_ALIGNMENT_QUANTIFICATION.out.logs
        .mix(RNASEQ_DIFFERENTIAL_EXPRESSION.out.logs)
        .mix(RUN_MANIFEST.out.reports)
}

workflow {
    GSE133183_RNASEQ_POST_QC()
}
