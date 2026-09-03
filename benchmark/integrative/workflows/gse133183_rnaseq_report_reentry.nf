nextflow.enable.dsl=2

include { RNASEQ_REPORT } from '../../../subworkflows/local/rnaseq/report'
include { RUN_MANIFEST } from '../../../modules/local/run_manifest/main'

/* Benchmark-only continuation after the audited post-QC run reached DESeq2. */
workflow GSE133183_RNASEQ_REPORT_REENTRY {
    main:
    root = params.case_root.toString()
    helixforge_root = file(params.helixforge_root, checkIfExists: true)
    sample_ids = ['GSM4817464', 'GSM4817465', 'GSM4817466', 'GSM4817467']
    metadata = file("${root}/results/pipeline_info/native_rnaseq/metadata/validated_metadata.csv", checkIfExists: true)
    annotation = file(params.precomputed_annotation, checkIfExists: true)
    reference_manifest = file("${root}/reference_bundle.normalized.manifest.json", checkIfExists: true)
    import_manifest = file("${root}/results/pipeline_info/native_import/tximport/import_manifest.json", checkIfExists: true)
    abundance = file("${root}/results/pipeline_info/native_import/tximport/tpm_matrix.tsv", checkIfExists: true)
    counts = file("${root}/results/pipeline_info/native_import/tximport/counts_matrix.tsv", checkIfExists: true)
    samples = file("${root}/results/pipeline_info/native_import/tximport/quant_samples.tsv", checkIfExists: true)
    de_results = file("${root}/results/pipeline_info/native_de/aggregate/DEGs_all_results.tsv", checkIfExists: true)
    de_manifest = file("${root}/results/pipeline_info/native_de/aggregate/de_manifest.json", checkIfExists: true)
    de_summary = file("${root}/results/pipeline_info/native_de/aggregate/DEGs_all_results.tsv", checkIfExists: true)
    contrast_results = file("${root}/pipeline/060-deg-analysis/gsk343_vs_dmso/contrasts/DEG_condition__GSK343_vs_DMSO.tsv", checkIfExists: true)
    normalized_counts = file("${root}/results/pipeline_info/native_de/aggregate/normalized_counts_condition.tsv", checkIfExists: true)
    genes = file("${root}/report_genes.txt", checkIfExists: true)
    report_target = params.rnaseq_report_outdir.toString()
    report_parameters = [
        title: params.rnaseq_report_title,
        expression_unit: 'TPM', life_stage_levels: 'unknown',
        stage_synonym_map: '', organism_specific: false
    ]
    report_parameters_base64 = groovy.json.JsonOutput.toJson(report_parameters)
        .bytes.encodeBase64().toString()
    report_meta = [
        id: 'rnaseq.report.candidate_genes', provider: 'candidate_genes_v1',
        target_dir: report_target, import_id: 'rnaseq.import', analysis_id: 'gse133183_k562'
    ]
    report_requests = channel.value(tuple(
        report_meta, import_manifest, abundance, samples, annotation,
        de_results, de_manifest, genes, report_parameters_base64
    ))
    RNASEQ_REPORT(report_requests)

    quant_records = channel.fromList(sample_ids).map { sample_id ->
        def id = "gse133183_k562.${sample_id}.quantification"
        def artifact = file("${root}/pipeline/040-alignment/quants/gse133183_k562/${sample_id}/quant.sf", checkIfExists: true)
        tuple([
            artifact_id: "${id}.transcript_abundance", artifact_type: 'transcript_abundance',
            assay: 'rnaseq', format: 'salmon_quant_sf', entity_level: 'transcript',
            contrast_id: null, sample_ids: [sample_id], condition: null, stage: null,
            mark_or_factor: null, peak_type: null, role: 'quantification',
            producer_manifest_id: id, producer_process: 'SALMON_QUANT',
            location: [kind: 'producer_relative', path: artifact.name, base_path: null, producer_manifest_id: id],
            source: [type: 'helixforge', name: 'Salmon', version: '1.10.3'], metadata: [dataset: 'gse133183_k562']
        ], artifact)
    }
    count_records = channel.value(tuple([
        artifact_id: 'rnaseq.import.gene_counts', artifact_type: 'gene_counts', assay: 'rnaseq',
        format: 'tsv', entity_level: 'gene', contrast_id: null, sample_ids: [], condition: null,
        stage: null, mark_or_factor: null, peak_type: null, role: 'counts',
        producer_manifest_id: 'rnaseq.import', producer_process: 'TXIMPORT',
        location: [kind: 'producer_relative', path: counts.name, base_path: null, producer_manifest_id: 'rnaseq.import'],
        source: [type: 'helixforge', name: 'salmon', version: null], metadata: [:]
    ], counts))
    abundance_records = channel.value(tuple([
        artifact_id: 'rnaseq.import.gene_abundance', artifact_type: 'gene_abundance', assay: 'rnaseq',
        format: 'tsv', entity_level: 'gene', contrast_id: null, sample_ids: [], condition: null,
        stage: null, mark_or_factor: null, peak_type: null, role: 'abundance',
        producer_manifest_id: 'rnaseq.import', producer_process: 'TXIMPORT',
        location: [kind: 'producer_relative', path: abundance.name, base_path: null, producer_manifest_id: 'rnaseq.import'],
        source: [type: 'helixforge', name: 'salmon', version: null], metadata: [:]
    ], abundance))
    de_summary_records = channel.value(tuple([
        artifact_id: 'gse133183_k562.differential_expression_summary', artifact_type: 'differential_expression_summary', assay: 'rnaseq',
        format: 'tsv', entity_level: 'gene', contrast_id: null, sample_ids: [], condition: null,
        stage: null, mark_or_factor: null, peak_type: null, role: 'combined_results',
        producer_manifest_id: 'gse133183_k562', producer_process: 'DE_AGGREGATE',
        location: [kind: 'producer_relative', path: de_summary.name, base_path: null, producer_manifest_id: 'gse133183_k562'],
        source: [type: 'helixforge', name: 'DESeq2', version: null], metadata: [:]
    ], de_summary))
    de_records = channel.value(tuple([
        artifact_id: 'gse133183_k562.condition.condition__GSK343_vs_DMSO.differential_expression',
        artifact_type: 'differential_expression', assay: 'rnaseq', format: 'tsv', entity_level: 'gene',
        contrast_id: 'condition__GSK343_vs_DMSO', sample_ids: [], condition: null, stage: null,
        mark_or_factor: null, peak_type: null, role: 'contrast_results',
        producer_manifest_id: 'gse133183_k562.condition.condition__GSK343_vs_DMSO', producer_process: 'DESEQ2_CONTRAST',
        location: [kind: 'producer_relative', path: contrast_results.name, base_path: null,
            producer_manifest_id: 'gse133183_k562.condition.condition__GSK343_vs_DMSO'],
        source: [type: 'helixforge', name: 'DESeq2', version: null], metadata: [model_id: 'gse133183_k562.condition']
    ], contrast_results))
    normalized_records = channel.value(tuple([
        artifact_id: 'gse133183_k562.condition.normalized_counts', artifact_type: 'normalized_counts', assay: 'rnaseq',
        format: 'tsv', entity_level: 'gene', contrast_id: null, sample_ids: [], condition: null,
        stage: null, mark_or_factor: null, peak_type: null, role: 'exploratory_expression',
        producer_manifest_id: 'gse133183_k562.condition', producer_process: 'DESEQ2_MODEL',
        location: [kind: 'producer_relative', path: normalized_counts.name, base_path: null, producer_manifest_id: 'gse133183_k562.condition'],
        source: [type: 'helixforge', name: 'DESeq2', version: null], metadata: [model_id: 'gse133183_k562.condition']
    ], normalized_counts))
    report_records = RNASEQ_REPORT.out.artifacts.map { meta, artifact ->
        tuple([
            artifact_id: "${meta.id}.report", artifact_type: 'rnaseq_report', assay: 'rnaseq',
            format: 'directory', entity_level: 'report', contrast_id: null, sample_ids: [], condition: null,
            stage: null, mark_or_factor: null, peak_type: null, role: 'report',
            producer_manifest_id: meta.id, producer_process: 'RNASEQ_GENE_REPORT',
            location: [kind: 'producer_relative', path: '.', base_path: null, producer_manifest_id: meta.id],
            source: [type: 'helixforge', name: meta.provider, version: '1.0'], metadata: [:]
        ], artifact)
    }
    terminal_records = quant_records.mix(count_records).mix(abundance_records)
        .mix(de_records).mix(de_summary_records).mix(normalized_records).mix(report_records)
    terminal_record_bundle = terminal_records.toList().map { records ->
        def ordered = records.sort { left, right -> left[0]['artifact_id'] <=> right[0]['artifact_id'] }
        tuple('terminal_manifest', ordered.collect { it[1] },
            groovy.json.JsonOutput.toJson(ordered.collect { it[0] }).bytes.encodeBase64().toString())
    }
    source_manifest_paths = sample_ids.collect { sample_id ->
        file("${root}/results/pipeline_info/native_quantification/salmon_quant/gse133183_k562.${sample_id}.quantification.manifest.json", checkIfExists: true)
    } + [import_manifest, de_manifest]
    terminal_source_manifests = channel.fromList(source_manifest_paths)
        .mix(RNASEQ_REPORT.out.manifest.map { _meta, manifest -> manifest })
        .toList().map { manifests -> tuple('terminal_manifest', manifests) }
    terminal_metadata = channel.value(tuple('terminal_manifest', metadata))
    terminal_reference = channel.value(tuple('terminal_manifest', reference_manifest))
    terminal_method = channel.value(tuple('terminal_manifest', 'salmon'))
    terminal_inputs = terminal_record_bundle.join(terminal_source_manifests)
        .join(terminal_metadata).join(terminal_reference).join(terminal_method)
        .map { _key, artifacts, descriptors, manifests, metadata_file, reference_file, method ->
            def safe_run = workflow.runName.replaceAll(/[^A-Za-z0-9._-]+/, '_')
            def manifest_meta = [id: "${safe_run}.rnaseq", assay: 'rnaseq']
            def run = [
                id: manifest_meta.id, run_id: workflow.sessionId.toString(), run_name: workflow.runName,
                helixforge_version: workflow.manifest.version ?: 'unknown', git_commit: workflow.commitId ?: 'unknown',
                nextflow_version: workflow.nextflow.version.toString(), profile: workflow.profile ?: '',
                quantification_method: method,
                source: [type: 'helixforge', name: 'HelixForge', version: workflow.manifest.version ?: 'unknown'],
                parameters: [benchmark_reentry: [boundary: 'post_deseq2', upstream_session: 'irreverent_curran']]
            ]
            tuple(manifest_meta, metadata_file, reference_file,
                file("${helixforge_root}/schemas/integration", checkIfExists: true), manifests, artifacts,
                file(params.rnaseq_de_spec, checkIfExists: true),
                groovy.json.JsonOutput.toJson(run).bytes.encodeBase64().toString(), descriptors)
        }
    RUN_MANIFEST(terminal_inputs)

    emit:
    completed = RUN_MANIFEST.out.status
    terminal_manifest = RUN_MANIFEST.out.artifacts
    terminal_bundle = RUN_MANIFEST.out.bundle
}

workflow {
    GSE133183_RNASEQ_REPORT_REENTRY()
}
