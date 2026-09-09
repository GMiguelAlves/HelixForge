nextflow.enable.dsl = 2

include { PEAK_ANNOTATION } from '../../../subworkflows/local/chipseq/peak_annotation'
include { TRACK_AGGREGATE } from '../../../modules/local/track_aggregate/main'
include { CHIPSEQ_FULL_REPORT_INPUT } from '../../../modules/local/chipseq_full_report_input/main'

workflow GSE133183_H3K27ME3_COMPLETION_REENTRY {
    main:
    required = [case_root: params.case_root, benchmark_root: params.benchmark_root]
    missing = required.findAll { _key, value -> value == null || value.toString().trim() == '' }.keySet()
    if (missing) error "H3K27me3 completion re-entry requires: ${missing.sort().join(', ')}"

    case_root = file(params.case_root, checkIfExists: true)
    benchmark_root = file(params.benchmark_root, checkIfExists: true)
    results = file("${case_root}/results", checkIfExists: true)
    reference = file("${benchmark_root}/reference/bundle/genome.fa", checkIfExists: true)
    annotation = file("${benchmark_root}/reference/bundle/annotation.gtf", checkIfExists: true)
    reference_manifest = file("${results}/pipeline_info/native_chipseq/reference/reference_bundle.manifest.json", checkIfExists: true)
    reference_document = new groovy.json.JsonSlurper().parse(reference_manifest.toFile())
    genome_id = (reference_document.genome_id ?: reference_document.build).toString()
    build = (reference_document.build ?: reference_document.genome_id).toString()

    consensus_prefix = 'gse133183_h3k27me3.gse133183_h3k27me3.H3K27me3'
    consensus_rows = ['DMSO', 'GSK343'].collect { condition ->
        def source_id = "${consensus_prefix}.${condition}.H3K27me3.${genome_id}.broad"
        def directory = file("${results}/chipseq/consensus/${source_id}/${source_id}.union.consensus_result", checkIfExists: true)
        def manifest = file("${results}/pipeline_info/native_chipseq/consensus/providers/${source_id}.union.manifest.json", checkIfExists: true)
        def document = new groovy.json.JsonSlurper().parse(manifest.toFile())
        def meta = [
            id: "${source_id}.annotation", source_id: document.id.toString(),
            genome_id: genome_id, organism: document.organism ?: 'Homo sapiens',
            condition: condition, target: 'H3K27me3', peak_type: 'broad',
        ]
        tuple(meta, file("${directory}/consolidated_peaks.bed", checkIfExists: true),
            manifest, reference, reference_manifest, annotation)
    }
    annotation_spec = [
        provider: params.chipseq_annotation_provider, mode: params.chipseq_annotation_mode,
        overlap_mode: params.chipseq_annotation_overlap_mode,
        promoter_upstream: params.chipseq_annotation_promoter_upstream as Integer,
        promoter_downstream: params.chipseq_annotation_promoter_downstream as Integer,
        max_tss_distance: params.chipseq_annotation_max_tss_distance,
        feature_priority: params.chipseq_annotation_feature_priority.toString().split(',').collect { value -> value.trim() },
        gene_assignment: params.chipseq_annotation_gene_assignment,
        strand_aware: params.chipseq_annotation_strand_aware.toString().toBoolean(),
        intergenic_policy: params.chipseq_annotation_intergenic_policy,
    ]
    annotation_spec_base64 = groovy.json.JsonOutput.toJson(annotation_spec).bytes.encodeBase64().toString()
    annotation_inputs = channel.fromList(consensus_rows.collect { meta, peaks, manifest, fasta, ref_manifest, gtf ->
        tuple(meta, peaks, manifest, fasta, ref_manifest, gtf, annotation_spec_base64)
    })
    PEAK_ANNOTATION(annotation_inputs)

    record_ids = ['SRR12773440', 'SRR12773441', 'SRR12773444', 'SRR12773445',
        'SRR12773446', 'SRR12773447', 'SRR12773450', 'SRR12773451']
    existing_track_ids = record_ids.collect { id -> "${id}.bigwig" } +
        ["aggregate.gse133183_h3k27me3.DMSO.H3K27me3.${genome_id}.bigwig",
         "aggregate.gse133183_h3k27me3.GSK343.H3K27me3.${genome_id}.bigwig"]
    existing_track_records = existing_track_ids.collect { id ->
        def directory = file("${results}/chipseq/tracks/${id}.track_result", checkIfExists: true)
        def manifest = file("${results}/pipeline_info/native_chipseq/tracks/provider/${id}.track_provider.manifest.json", checkIfExists: true)
        tuple([id: id], directory, manifest,
            file("${results}/pipeline_info/native_chipseq/tracks/statistics/${id}.track_statistics.json", checkIfExists: true),
            file("${results}/pipeline_info/native_chipseq/tracks/statistics/${id}.track_statistics.manifest.json", checkIfExists: true))
    }
    aggregate_track_input = channel.value(existing_track_records).map { records ->
        tuple([id: 'chipseq.tracks.aggregate'], records.collect { record -> record[1] }, records.collect { record -> record[2] },
            records.collect { record -> record[3] }, records.collect { record -> record[4] })
    }
    TRACK_AGGREGATE(aggregate_track_input)

    base_manifests = [
        file("${results}/pipeline_info/native_chipseq/metadata/chipseq_metadata.manifest.json", checkIfExists: true),
        reference_manifest,
        file("${results}/pipeline_info/native_chipseq/peak_qc/aggregate/peak_qc_manifest.json", checkIfExists: true),
        file("${results}/pipeline_info/native_chipseq/consensus/aggregate/consensus_manifest.json", checkIfExists: true),
        file("${case_root}/db_reentry_results/pipeline_info/native_chipseq/differential_binding/aggregate/db_manifest.json", checkIfExists: true),
        file("${case_root}/db_reentry_results/differential_binding/differential_binding_results/contrasts/${consensus_prefix}.H3K27me3.${genome_id}.broad/GSK343_vs_DMSO/contrast_manifest.json", checkIfExists: true),
    ]
    base_manifests.addAll(record_ids.collect { id ->
        file("${results}/pipeline_info/native_alignment/bowtie2_align/${id}.manifest.json", checkIfExists: true)
    })
    base_manifests.addAll(record_ids.collect { id ->
        file("${results}/pipeline_info/native_chipseq/bam_final/${id}.bam_final.manifest.json", checkIfExists: true)
    })
    base_manifests.addAll(['SRR12773440', 'SRR12773441', 'SRR12773446', 'SRR12773447'].collect { id ->
        file("${results}/pipeline_info/native_chipseq/peak_calling/aggregate/${id}.H3K27me3.broad.macs3.manifest.json", checkIfExists: true)
    })
    full_manifests = channel.fromList(base_manifests)
        .mix(PEAK_ANNOTATION.out.manifest.map { _meta, manifest -> manifest })
        .mix(TRACK_AGGREGATE.out.manifest.map { _meta, manifest -> manifest })
    semantic_artifacts = channel.fromList([
        file("${results}/pipeline_info/native_chipseq/peak_qc/aggregate/peak_qc_summary.json", checkIfExists: true),
        file("${results}/pipeline_info/native_chipseq/consensus/aggregate/consolidation_summary.json", checkIfExists: true),
        file("${case_root}/db_reentry_results/differential_binding/differential_binding_results/differential_binding_summary.tsv", checkIfExists: true),
    ]).mix(PEAK_ANNOTATION.out.artifacts.map { _meta, directory -> file("${directory}/statistics.tsv", checkIfExists: true) })
      .mix(TRACK_AGGREGATE.out.artifacts.map { _meta, directory -> file("${directory}/tracks.tsv", checkIfExists: true) })
    report_materials = full_manifests.toList().map { manifests -> tuple('report', manifests.sort { a, b -> a.name <=> b.name }) }
        .join(semantic_artifacts.toList().map { artifacts -> tuple('report', artifacts.sort { a, b -> a.name <=> b.name }) })
    report_meta = [id: 'gse133183_h3k27me3.chipseq_report', project_id: 'gse133183_h3k27me3',
        dataset: 'gse133183_h3k27me3', genome_id: genome_id, build: build, organism: 'Homo sapiens']
    report_input = channel.value(tuple('report', report_meta)).join(report_materials)
        .map { _key, meta, manifests, artifacts -> tuple(meta, manifests, artifacts) }
    CHIPSEQ_FULL_REPORT_INPUT(report_input)

    emit:
    completed = CHIPSEQ_FULL_REPORT_INPUT.out.status
    report_inventory = CHIPSEQ_FULL_REPORT_INPUT.out.artifacts
    annotation = PEAK_ANNOTATION.out.artifacts
    tracks = TRACK_AGGREGATE.out.artifacts
}

workflow { GSE133183_H3K27ME3_COMPLETION_REENTRY() }
