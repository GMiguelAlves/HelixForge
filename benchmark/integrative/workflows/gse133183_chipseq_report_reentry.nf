nextflow.enable.dsl = 2

include { CHIPSEQ_REPORT } from '../../../subworkflows/local/chipseq/report'
include { RUN_MANIFEST } from '../../../modules/local/run_manifest/main'

def resolveInventoryPath(inventoryFile, value) {
    def candidate = java.nio.file.Paths.get(value.toString())
    candidate.isAbsolute() ? value.toString() : "${inventoryFile.parent}/${value}"
}

workflow GSE133183_CHIPSEQ_REPORT_REENTRY {
    main:
    required = [
        helixforge_root: params.helixforge_root, report_inventory: params.report_inventory,
        metadata: params.metadata, reference: params.reference_manifest,
        contrast: params.contrast_spec, differential: params.db_results,
        annotation: params.annotation_results, tracks: params.track_artifact,
        peak_qc: params.peak_qc_summary, consensus: params.consensus_artifact,
        mark: params.mark, peak_type: params.peak_type, contrast_id: params.contrast_id,
    ]
    missing = required.findAll { _key, value -> value == null || value.toString().trim() == '' }.keySet()
    if (missing) error "ChIP-seq report re-entry requires: ${missing.sort().join(', ')}"

    helixforge_root = file(params.helixforge_root, checkIfExists: true)
    inventory_file = file(params.report_inventory, checkIfExists: true)
    inventory = new groovy.json.JsonSlurper().parse(inventory_file.toFile())
    if (inventory.schema_version != '1.0' || inventory.type != 'chipseq_report_input') {
        error 'Report re-entry requires a chipseq_report_input v1 inventory'
    }
    manifest_files = inventory.components.collect { entry ->
        file(resolveInventoryPath(inventory_file, entry.manifest), checkIfExists: true)
    }
    semantic_artifacts = inventory.components.collectMany { entry ->
        (entry.artifacts ?: []).collect { value ->
            file(resolveInventoryPath(inventory_file, value), checkIfExists: true)
        }
    }
    report_id = "${inventory.project.project_id}.chipseq_report".replaceAll(/[^A-Za-z0-9._-]+/, '_')
    report_meta = [
        id: report_id, project_id: inventory.project.project_id.toString(),
        dataset: inventory.project.dataset.toString(), genome_id: inventory.project.genome_id.toString(),
        build: inventory.project.build.toString(),
    ]
    presentation = [provider: 'html_v1', title: params.report_title, language: params.report_language]
    presentation_base64 = groovy.json.JsonOutput.toJson(presentation).bytes.encodeBase64().toString()
    CHIPSEQ_REPORT(channel.value(tuple(
        report_meta, inventory_file, manifest_files, semantic_artifacts, presentation_base64
    )))

    metadata = file(params.metadata, checkIfExists: true)
    reference_manifest = file(params.reference_manifest, checkIfExists: true)
    contrast_spec = file(params.contrast_spec, checkIfExists: true)
    db_results = file(params.db_results, checkIfExists: true)
    annotation_results = file(params.annotation_results, checkIfExists: true)
    track_artifact = file(params.track_artifact, checkIfExists: true)
    peak_qc_summary = file(params.peak_qc_summary, checkIfExists: true)
    consensus_artifact = file(params.consensus_artifact, checkIfExists: true)
    mark = params.mark.toString()
    peak_type = params.peak_type.toString()
    contrast_id = params.contrast_id.toString()
    prefix = inventory.project.project_id.toString()

    db_records = channel.value(tuple([
        artifact_id: "${prefix}.${mark}.differential_binding", artifact_type: 'differential_binding',
        assay: 'chipseq', format: 'tsv', entity_level: 'peak', contrast_id: contrast_id,
        sample_ids: [], condition: null, stage: null, mark_or_factor: mark,
        marks_or_factors: [], peak_type: peak_type, role: 'contrast_results',
        producer_manifest_id: "${prefix}.${contrast_id}", producer_process: 'DESEQ2_DB_CONTRAST',
        location: [kind: 'producer_relative', path: db_results.name, base_path: null,
            producer_manifest_id: "${prefix}.${contrast_id}"],
        source: [type: 'helixforge', name: 'DESeq2', version: null], metadata: [benchmark_reentry: true],
    ], db_results))
    annotation_records = channel.value(tuple([
        artifact_id: "${prefix}.${mark}.peak_gene_annotation", artifact_type: 'peak_gene_annotation',
        assay: 'chipseq', format: 'tsv', entity_level: 'peak', contrast_id: null,
        sample_ids: [], condition: null, stage: null, mark_or_factor: mark,
        marks_or_factors: [], peak_type: peak_type, role: 'peak_gene_associations',
        producer_manifest_id: "${prefix}.peak_annotation", producer_process: 'PEAK_ANNOTATION_AGGREGATE',
        location: [kind: 'producer_relative', path: annotation_results.name, base_path: null,
            producer_manifest_id: "${prefix}.peak_annotation"],
        source: [type: 'helixforge', name: 'native_annotation', version: '1.0'], metadata: [:],
    ], annotation_results))
    track_records = channel.value(tuple([
        artifact_id: "${prefix}.${mark}.signal_tracks", artifact_type: 'signal_track',
        assay: 'chipseq', format: 'directory', entity_level: 'sample', contrast_id: null,
        sample_ids: [], condition: null, stage: null, mark_or_factor: mark,
        marks_or_factors: [], peak_type: peak_type, role: 'visualization',
        producer_manifest_id: "${prefix}.tracks", producer_process: 'TRACK_AGGREGATE',
        location: [kind: 'producer_relative', path: track_artifact.name, base_path: null,
            producer_manifest_id: "${prefix}.tracks"],
        source: [type: 'helixforge', name: 'deepTools', version: null], metadata: [:],
    ], track_artifact))
    peak_qc_records = channel.value(tuple([
        artifact_id: "${prefix}.${mark}.peak_qc", artifact_type: 'peak_qc', assay: 'chipseq',
        format: 'tsv', entity_level: 'peak', contrast_id: null, sample_ids: [], condition: null,
        stage: null, mark_or_factor: mark, marks_or_factors: [], peak_type: peak_type,
        role: 'quality_control', producer_manifest_id: "${prefix}.peak_qc",
        producer_process: 'PEAK_QC_AGGREGATE',
        location: [kind: 'producer_relative', path: peak_qc_summary.name, base_path: null,
            producer_manifest_id: "${prefix}.peak_qc"],
        source: [type: 'helixforge', name: 'Peak QC API', version: '1.0'], metadata: [:],
    ], peak_qc_summary))
    consensus_records = channel.value(tuple([
        artifact_id: "${prefix}.${mark}.consensus_peaks", artifact_type: 'consensus_peaks',
        assay: 'chipseq', format: 'bed', entity_level: 'peak', contrast_id: null,
        sample_ids: [], condition: params.consensus_condition, stage: null, mark_or_factor: mark,
        marks_or_factors: [], peak_type: peak_type, role: 'consolidated_peaks',
        producer_manifest_id: "${prefix}.consensus", producer_process: 'CONSENSUS_INTERVALS',
        location: [kind: 'producer_relative', path: consensus_artifact.name, base_path: null,
            producer_manifest_id: "${prefix}.consensus"],
        source: [type: 'helixforge', name: 'union', version: '1.0'], metadata: [:],
    ], consensus_artifact))
    report_records = CHIPSEQ_REPORT.out.artifacts.map { meta, directory ->
        tuple([
            artifact_id: "${meta.id}.report", artifact_type: 'chipseq_report', assay: 'chipseq',
            format: 'directory', entity_level: 'report', contrast_id: null, sample_ids: [],
            condition: null, stage: null, mark_or_factor: null, marks_or_factors: [],
            peak_type: null, role: 'report', producer_manifest_id: meta.id,
            producer_process: 'REPORT_GENERATOR',
            location: [kind: 'producer_relative', path: '.', base_path: null, producer_manifest_id: meta.id],
            source: [type: 'helixforge', name: 'html_v1', version: '1.0'],
            metadata: [benchmark_reentry: true],
        ], directory)
    }
    terminal_records = db_records.mix(annotation_records).mix(track_records)
        .mix(peak_qc_records).mix(consensus_records).mix(report_records)
    terminal_record_bundle = terminal_records.toList().map { records ->
        def ordered = records.sort { left, right -> left[0].artifact_id <=> right[0].artifact_id }
        tuple('terminal_manifest', ordered.collect { it[1] },
            groovy.json.JsonOutput.toJson(ordered.collect { it[0] }).bytes.encodeBase64().toString())
    }
    terminal_source_manifests = channel.fromList(manifest_files)
        .mix(CHIPSEQ_REPORT.out.manifest.map { _meta, manifest -> manifest })
        .toList().map { manifests -> tuple('terminal_manifest', manifests) }
    terminal_metadata = channel.value(tuple('terminal_manifest', metadata))
    terminal_reference = channel.value(tuple('terminal_manifest', reference_manifest))
    terminal_contrast = channel.value(tuple('terminal_manifest', contrast_spec))
    terminal_inputs = terminal_record_bundle.join(terminal_source_manifests)
        .join(terminal_metadata).join(terminal_reference).join(terminal_contrast)
        .map { _key, artifacts, descriptors, manifests, metadata_file, reference_file, contrast_file ->
            def safe_run = workflow.runName.replaceAll(/[^A-Za-z0-9._-]+/, '_')
            def manifest_meta = [id: "${safe_run}.chipseq", assay: 'chipseq']
            def run = [
                id: manifest_meta.id, run_id: workflow.sessionId.toString(), run_name: workflow.runName,
                helixforge_version: workflow.manifest.version ?: 'unknown',
                git_commit: workflow.commitId ?: 'unknown', nextflow_version: workflow.nextflow.version.toString(),
                profile: workflow.profile ?: '',
                source: [type: 'helixforge', name: 'HelixForge', version: workflow.manifest.version ?: 'unknown'],
                parameters: [benchmark_reentry: [boundary: 'post_differential_binding', mark: mark]],
            ]
            tuple(manifest_meta, metadata_file, reference_file,
                file("${helixforge_root}/schemas/integration", checkIfExists: true), manifests, artifacts,
                contrast_file, groovy.json.JsonOutput.toJson(run).bytes.encodeBase64().toString(), descriptors)
        }
    RUN_MANIFEST(terminal_inputs)

    emit:
    completed = RUN_MANIFEST.out.status
    terminal_manifest = RUN_MANIFEST.out.artifacts
    terminal_bundle = RUN_MANIFEST.out.bundle
}

workflow { GSE133183_CHIPSEQ_REPORT_REENTRY() }
