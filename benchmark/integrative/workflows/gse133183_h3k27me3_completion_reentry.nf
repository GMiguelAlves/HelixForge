nextflow.enable.dsl = 2

include { PEAK_ANNOTATION } from '../../../subworkflows/local/chipseq/peak_annotation'
include { TRACK_CONTEXT } from '../../../modules/local/track_context/main'
include { TRACK_PROVIDER } from '../../../modules/local/track_provider/main'
include { TRACK_STATISTICS } from '../../../modules/local/track_statistics/main'
include { TRACK_AGGREGATE } from '../../../modules/local/track_aggregate/main'
include { CHIPSEQ_FULL_REPORT_INPUT } from '../../../modules/local/chipseq_full_report_input/main'

def matchedFiles(pattern) {
    def matches = file(pattern, checkIfExists: true)
    if (matches instanceof List) {
        return matches
    }
    return [matches]
}

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

    dmso_ids = ['SRR12773440', 'SRR12773441']
    dmso_bams = dmso_ids.collect { id -> file("${results}/060-filtering/${id}/${id}.filtered.bam", checkIfExists: true) }
    dmso_bais = dmso_ids.collect { id -> file("${results}/060-filtering/${id}/${id}.filtered.bam.bai", checkIfExists: true) }
    dmso_manifests = dmso_ids.collect { id -> file("${results}/pipeline_info/native_chipseq/bam_final/${id}.bam_final.manifest.json", checkIfExists: true) }
    dmso_documents = dmso_manifests.collect { manifest -> new groovy.json.JsonSlurper().parse(manifest.toFile()) }
    dmso_meta = [
        id: "aggregate.gse133183_h3k27me3.DMSO.H3K27me3.${genome_id}.bigwig",
        track_role: 'aggregate', record_id: null, record_ids: dmso_ids,
        sample_ids: dmso_documents.collect { document -> document.sample_id.toString() }, dataset: 'gse133183_h3k27me3',
        condition: 'DMSO', target: 'H3K27me3', is_control: false,
        biological_replicates: dmso_documents.collect { document -> (document.biological_replicate ?: '').toString() },
        technical_replicates: dmso_documents.collect { document -> (document.technical_replicate ?: '1').toString() },
        genome_id: genome_id, build: build,
    ]
    track_spec = [provider: 'deeptools_bamcoverage_v1', track_format: 'bigwig', bin_size: 10,
        normalization: 'CPM', effective_genome_size: null, scale_factor: 1.0,
        extend_reads: false, fragment_mode: 'reads', strand: 'unstranded', additional_filters: 'none']
    track_spec_base64 = groovy.json.JsonOutput.toJson(track_spec).bytes.encodeBase64().toString()
    TRACK_CONTEXT(channel.value(tuple(dmso_meta, dmso_bams, dmso_bais, dmso_manifests,
        reference, reference_manifest, track_spec_base64)))
    missing_track_sources = channel.value(tuple(dmso_meta.id, dmso_meta, dmso_bams, dmso_bais))
    missing_track_provider = TRACK_CONTEXT.out.artifacts.map { meta, request -> tuple(meta.id, request) }
        .join(missing_track_sources)
        .map { _id, request, meta, bams, bais -> tuple(meta, bams, bais, request) }
    TRACK_PROVIDER(missing_track_provider)
    missing_track_statistics = TRACK_PROVIDER.out.artifacts.map { meta, directory -> tuple(meta.id, meta, directory) }
        .join(TRACK_PROVIDER.out.manifest.map { meta, manifest -> tuple(meta.id, manifest) })
        .map { _id, meta, directory, manifest -> tuple(meta, directory, manifest) }
    TRACK_STATISTICS(missing_track_statistics)

    existing_track_dirs = matchedFiles("${results}/chipseq/tracks/*.track_result")
    existing_track_records = existing_track_dirs.collect { directory ->
        def manifest = file("${directory}/manifest.json", checkIfExists: true)
        def document = new groovy.json.JsonSlurper().parse(manifest.toFile())
        def id = document.id.toString()
        tuple([id: id], directory, manifest,
            file("${results}/pipeline_info/native_chipseq/tracks/statistics/${id}.track_statistics.json", checkIfExists: true),
            file("${results}/pipeline_info/native_chipseq/tracks/statistics/${id}.track_statistics.manifest.json", checkIfExists: true))
    }
    if (existing_track_records.size() != 9) {
        error "Expected 9 completed H3K27me3 track providers before re-entry; observed ${existing_track_records.size()}"
    }
    new_track_record = TRACK_PROVIDER.out.artifacts.map { meta, directory -> tuple(meta.id, meta, directory) }
        .join(TRACK_PROVIDER.out.manifest.map { meta, manifest -> tuple(meta.id, manifest) })
        .join(TRACK_STATISTICS.out.artifacts.map { meta, statistics, _table -> tuple(meta.id, statistics) })
        .join(TRACK_STATISTICS.out.manifest.map { meta, manifest -> tuple(meta.id, manifest) })
        .map { _id, meta, directory, manifest, statistics, statistics_manifest ->
            tuple(meta, directory, manifest, statistics, statistics_manifest)
        }
    aggregate_track_input = channel.fromList(existing_track_records).mix(new_track_record).toList().map { records ->
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
    base_manifests.addAll(matchedFiles("${results}/pipeline_info/native_alignment/bowtie2_align/*.manifest.json"))
    base_manifests.addAll(matchedFiles("${results}/pipeline_info/native_chipseq/bam_final/*.manifest.json"))
    base_manifests.addAll(matchedFiles("${results}/pipeline_info/native_chipseq/peak_calling/*.manifest.json"))
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
