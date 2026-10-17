include { CHIPSEQ_CONTINUATION_CONTEXT } from '../../../modules/local/chipseq_continuation_context/main'
include { PEAK_ANNOTATION } from './peak_annotation'
include { TRACK_GENERATION } from './tracks'
include { CHIPSEQ_FULL_REPORT_INPUT } from '../../../modules/local/chipseq_full_report_input/main'
include { CHIPSEQ_REPORT } from './report'
include { RUN_MANIFEST } from '../../../modules/local/run_manifest/main'

def continuation_descriptor(meta, type, artifact, level, role, producer) {
    [artifact_id: "${meta.id}.${type}", artifact_type: type, assay: 'chipseq', format: artifact.toFile().isDirectory() ? 'directory' : (type == 'aligned_bam' ? 'bam' : (type in ['consensus_peaks', 'idr_peaks'] ? 'bed' : 'tsv')),
     entity_level: level, contrast_id: null, sample_ids: meta.sample_ids ?: [], condition: meta.condition,
     stage: null, mark_or_factor: meta.target, marks_or_factors: meta.marks_or_factors ?: [], peak_type: meta.peak_type,
     role: role, producer_manifest_id: meta.source_manifest_id ?: meta.id, producer_process: producer,
     location: [kind: 'producer_relative', path: type == 'chipseq_report' ? '.' : artifact.name, base_path: null, producer_manifest_id: meta.source_manifest_id ?: meta.id],
     source: [type: 'helixforge', name: 'ChIP-seq API', version: '1.0'], metadata: [:]]
}

workflow CHIPSEQ_POST_CONSENSUS {
    take:
    continuation_inputs

    main:
    CHIPSEQ_CONTINUATION_CONTEXT(continuation_inputs)
    bundle = CHIPSEQ_CONTINUATION_CONTEXT.out.artifacts.map { meta, plan, paths ->
        tuple(meta, new groovy.json.JsonSlurper().parse(plan.toFile()), paths)
    }
    def annotation_spec = [provider: params.chipseq_annotation_provider, mode: params.chipseq_annotation_mode,
        overlap_mode: params.chipseq_annotation_overlap_mode, promoter_upstream: params.chipseq_annotation_promoter_upstream as Integer,
        promoter_downstream: params.chipseq_annotation_promoter_downstream as Integer, max_tss_distance: params.chipseq_annotation_max_tss_distance,
        feature_priority: params.chipseq_annotation_feature_priority.toString().split(',').collect { value -> value.trim() },
        gene_assignment: params.chipseq_annotation_gene_assignment, strand_aware: params.chipseq_annotation_strand_aware.toString().toBoolean(),
        intergenic_policy: params.chipseq_annotation_intergenic_policy]
    def annotation_encoded = groovy.json.JsonOutput.toJson(annotation_spec).bytes.encodeBase64().toString()
    annotation_inputs = bundle.flatMap { _meta, plan, paths -> plan.peaks.collect { entry ->
        tuple(entry.meta + [id: "${entry.meta.id}.annotation", source_id: entry.meta.id], paths[entry.peaks], paths[entry.manifest],
            paths[plan.reference.fasta], paths[plan.reference.manifest], paths[plan.reference.annotation], annotation_encoded)
    } }
    PEAK_ANNOTATION(annotation_inputs)

    def track_spec = [provider: params.chipseq_track_provider, track_format: params.chipseq_track_format,
        bin_size: params.chipseq_track_bin_size as Integer, normalization: params.chipseq_track_normalization,
        effective_genome_size: params.chipseq_track_effective_genome_size != null ? params.chipseq_track_effective_genome_size as Integer : null,
        scale_factor: params.chipseq_track_scale_factor as Double, extend_reads: params.chipseq_track_extend_reads.toString().toBoolean(),
        fragment_mode: params.chipseq_track_fragment_mode, strand: params.chipseq_track_strand, additional_filters: params.chipseq_track_additional_filters]
    def track_encoded = groovy.json.JsonOutput.toJson(track_spec).bytes.encodeBase64().toString()
    if (params.chipseq_track_aggregate.toString().toBoolean() && params.chipseq_track_aggregate_scope != 'condition_target') {
        error 'Track aggregate scope must be condition_target'
    }
    track_inputs = bundle.flatMap { _meta, plan, paths ->
        def groups = plan.records.collect { record -> [record] }
        if (params.chipseq_track_aggregate.toString().toBoolean()) {
            groups += plan.records.findAll { record -> !record.meta.is_control }
                .groupBy { record -> [record.meta.dataset, record.meta.condition, record.meta.target] }.values().toList()
        }
        groups.withIndex().collect { records, index ->
            def ordered = records.sort { left, right -> left.record_id <=> right.record_id }
            def first = ordered[0].meta
            def role = index < plan.records.size() ? 'individual' : 'aggregate'
            def id = role == 'individual' ? "${first.id}.bigwig" : "aggregate.${first.dataset}.${first.condition}.${first.target}.${first.genome_id}.bigwig".replaceAll(/[^A-Za-z0-9._-]+/, '_')
            def meta = [id: id, track_role: role, record_id: role == 'individual' ? first.id : null,
                record_ids: ordered.collect { record -> record.record_id }, sample_ids: ordered.collect { record -> record.meta.sample_id },
                biological_replicates: ordered.collect { record -> record.meta.biological_replicate }, technical_replicates: ordered.collect { record -> record.meta.technical_replicate },
                dataset: first.dataset, condition: first.condition, target: first.target, is_control: first.is_control,
                genome_id: plan.project.genome_id, build: plan.project.build]
            tuple(meta, ordered.collect { record -> paths[record.bam] }, ordered.collect { record -> paths[record.bai] },
                ordered.collect { record -> paths[record.manifest] }, paths[plan.reference.fasta], paths[plan.reference.manifest], track_encoded)
        }
    }
    TRACK_GENERATION(track_inputs)
    source_files = bundle.flatMap { _meta, plan, paths ->
        ([plan.metadata.manifest, plan.reference.manifest] + plan.records.collect { record -> record.manifest } +
            plan.peaks.collect { entry -> entry.manifest } + (plan.source_manifests ?: [])).unique().collect { index -> paths[index] }
    }
    all_manifests = source_files.mix(PEAK_ANNOTATION.out.manifest.map { _meta, manifest -> manifest })
        .mix(TRACK_GENERATION.out.manifest.map { _meta, manifest -> manifest })
    semantic = PEAK_ANNOTATION.out.artifacts.map { _meta, directory -> file("${directory}/statistics.tsv", checkIfExists: true) }
        .mix(TRACK_GENERATION.out.artifacts.map { _meta, directory -> file("${directory}/tracks.tsv", checkIfExists: true) })
    materials = all_manifests.toList().map { paths -> tuple('report', paths) }
        .join(semantic.toList().map { paths -> tuple('report', paths) })
    report_meta = bundle.map { _meta, plan, _paths ->
        tuple('report', plan.project + [id: "${plan.project.project_id}.chipseq_report",
            required_components: ['metadata', 'reference', 'bam', 'consensus_idr', 'annotation', 'tracks']])
    }
    CHIPSEQ_FULL_REPORT_INPUT(report_meta.join(materials).map { _key, meta, manifests, artifacts -> tuple(meta, manifests, artifacts) })
    def presentation = groovy.json.JsonOutput.toJson([provider: params.chipseq_report_provider, title: params.chipseq_report_title, language: params.chipseq_report_language]).bytes.encodeBase64().toString()
    report_records = CHIPSEQ_FULL_REPORT_INPUT.out.artifacts.map { meta, inventory -> tuple('report', meta, inventory) }
        .join(materials).map { _key, meta, inventory, manifests, artifacts -> tuple(meta, inventory, manifests, artifacts, presentation) }
    CHIPSEQ_REPORT(report_records)

    upstream_records = bundle.flatMap { _meta, plan, paths ->
        def bams = plan.records.collect { record ->
            def meta = record.meta + [sample_ids: [record.meta.sample_id]]
            tuple(continuation_descriptor(meta, 'aligned_bam', paths[record.bam], 'sample', 'final_bam', 'BAM_INDEX_QC'), paths[record.bam])
        }
        bams + plan.peaks.collect { entry ->
            tuple(continuation_descriptor(entry.meta, entry.meta.artifact_type, paths[entry.peaks], 'peak', 'consolidated_peaks', 'CONSENSUS_IDR'), paths[entry.peaks])
        }
    }
    marks_bundle = bundle.map { _meta, plan, _paths -> [values: plan.peaks.collect { entry -> entry.meta.target }.unique()] }
    annotation_records = PEAK_ANNOTATION.out.artifacts.combine(marks_bundle).map { meta, directory, marks ->
        def artifact = file("${directory}/peak_gene_associations.tsv", checkIfExists: true)
        tuple(continuation_descriptor(meta + [marks_or_factors: marks.values], 'peak_gene_annotation', artifact, 'peak', 'peak_gene_associations', 'PEAK_ANNOTATION_AGGREGATE'), artifact)
    }
    track_records = TRACK_GENERATION.out.artifacts.map { meta, directory ->
        def artifact = file("${directory}/tracks", checkIfExists: true)
        tuple(continuation_descriptor(meta, 'signal_track', artifact, 'sample', 'visualization', 'TRACK_AGGREGATE'), artifact)
    }
    report_artifacts = CHIPSEQ_REPORT.out.artifacts.map { meta, directory ->
        tuple(continuation_descriptor(meta, 'chipseq_report', directory, 'report', 'report', 'REPORT_GENERATOR'), directory)
    }
    terminal_records = upstream_records.mix(annotation_records).mix(track_records).mix(report_artifacts)
        .toList().map { rows ->
            def ordered = rows.sort { left, right -> left[0].artifact_id <=> right[0].artifact_id }
            tuple('terminal', ordered.collect { row -> row[1] }, groovy.json.JsonOutput.toJson(ordered.collect { row -> row[0] }).bytes.encodeBase64().toString())
        }
    terminal_sources = all_manifests.mix(CHIPSEQ_REPORT.out.manifest.map { _meta, manifest -> manifest }).toList().map { paths -> tuple('terminal', paths) }
    terminal_inputs = terminal_records.join(terminal_sources)
        .join(bundle.map { meta, plan, paths -> tuple('terminal', meta, plan, paths) })
        .map { _key, artifacts, descriptors, manifests, _meta, plan, paths ->
            def meta = [id: "${workflow.runName}.chipseq".replaceAll(/[^A-Za-z0-9._-]+/, '_'), assay: 'chipseq']
            def run = [id: meta.id, run_id: workflow.sessionId.toString(), run_name: workflow.runName,
                helixforge_version: workflow.manifest.version ?: 'unknown', git_commit: workflow.commitId ?: 'unknown',
                nextflow_version: workflow.nextflow.version.toString(), profile: workflow.profile ?: '',
                parameters: [chipseq_run_mode: 'post_consensus', differential_binding: 'not_requested', source_manifest_ids: plan.source_manifest_ids]]
            tuple(meta, paths[plan.metadata.table], paths[plan.reference.manifest], file("${projectDir}/schemas/integration"),
                manifests, artifacts, [], groovy.json.JsonOutput.toJson(run).bytes.encodeBase64().toString(), descriptors)
        }
    RUN_MANIFEST(terminal_inputs)

    emit:
    completed = RUN_MANIFEST.out.status
    terminal_manifest = RUN_MANIFEST.out.artifacts
    terminal_bundle = RUN_MANIFEST.out.bundle
    report_input = CHIPSEQ_FULL_REPORT_INPUT.out.artifacts
    report = CHIPSEQ_REPORT.out.artifacts
    logs = CHIPSEQ_CONTINUATION_CONTEXT.out.reports.mix(PEAK_ANNOTATION.out.reports).mix(TRACK_GENERATION.out.reports)
        .mix(CHIPSEQ_FULL_REPORT_INPUT.out.reports).mix(CHIPSEQ_REPORT.out.reports).mix(RUN_MANIFEST.out.reports)
}
