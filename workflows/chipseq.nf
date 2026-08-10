include { CHIPSEQ_REFERENCE }    from '../subworkflows/local/chipseq/reference'
include { CHIPSEQ_QC_ALIGNMENT } from '../subworkflows/local/chipseq/qc_alignment'
include { CHIPSEQ_PEAK_ANALYSIS } from '../subworkflows/local/chipseq/peak_analysis'
include { CHIPSEQ_NATIVE_FOUNDATION } from '../subworkflows/local/chipseq/native_foundation'
include { PEAK_ANNOTATION } from '../subworkflows/local/chipseq/peak_annotation'
include { TRACK_GENERATION } from '../subworkflows/local/chipseq/tracks'
include { LEGACY_STEP as CHIPSEQ_LEGACY_PEAKS } from '../modules/local/legacy_step/main'
include { LEGACY_STEP as CHIPSEQ_LEGACY_CONSENSUS } from '../modules/local/legacy_step/main'
include { LEGACY_STEP as CHIPSEQ_LEGACY_DIFFERENTIAL } from '../modules/local/legacy_step/main'
include { LEGACY_STEP as CHIPSEQ_LEGACY_ANNOTATION } from '../modules/local/legacy_step/main'
include { LEGACY_STEP as CHIPSEQ_LEGACY_TRACKS } from '../modules/local/legacy_step/main'


def resolve_track_inventory_location(inventory_file, value) {
    def candidate = java.nio.file.Paths.get(value.toString())
    candidate.isAbsolute() ? value.toString() : "${inventory_file.parent}/${value}"
}

workflow CHIPSEQ {
    take:
    seed

    main:
    config_file = file(params.chipseq_config, checkIfExists: true)
    legacy_root = "${projectDir}/pipelines/chipseq/legacy"
    run_mode = params.chipseq_run_mode.toString().toLowerCase()
    native_peak_calling = params.chipseq_native_peak_calling.toString().toBoolean()
    native_peak_qc = params.chipseq_native_peak_qc.toString().toBoolean()
    native_consensus = params.chipseq_native_consensus.toString().toBoolean()
    native_differential = params.chipseq_native_differential_binding.toString().toBoolean()
    native_annotation = params.chipseq_native_peak_annotation.toString().toBoolean()
    native_tracks = params.chipseq_native_tracks.toString().toBoolean()
    if (!(run_mode in ['qc', 'alignment', 'post_alignment', 'peaks', 'peak_qc', 'consensus', 'idr', 'differential_binding', 'annotation', 'tracks', 'full'])) {
        error "Unknown chipseq_run_mode '${params.chipseq_run_mode}'. Use qc, alignment, post_alignment, peaks, peak_qc, consensus, idr, differential_binding, annotation, tracks, or full."
    }

    native_mode = params.chipseq_native_foundation && (
        run_mode in ['qc', 'alignment', 'post_alignment'] ||
        (run_mode in ['peaks', 'peak_qc'] && native_peak_calling) ||
        (run_mode in ['consensus', 'idr'] && native_peak_calling && native_peak_qc && native_consensus) ||
        (run_mode == 'differential_binding' && native_peak_calling && native_peak_qc && native_consensus && native_differential)
    )

    if (run_mode == 'tracks' && native_tracks) {
        if (params.chipseq_tracks_input_manifest == null || params.chipseq_tracks_input_manifest.toString().trim() == '') {
            error 'Native tracks mode requires --chipseq_tracks_input_manifest'
        }
        tracks_inventory_file = file(params.chipseq_tracks_input_manifest, checkIfExists: true)
        tracks_inventory = new groovy.json.JsonSlurper().parse(tracks_inventory_file.toFile())
        if (tracks_inventory.schema_version != '1.0' || tracks_inventory.type != 'track_generation_input') {
            error 'Track inventory must declare schema_version=1.0 and type=track_generation_input'
        }
        if (!(tracks_inventory.records instanceof List) || tracks_inventory.records.isEmpty()) {
            error 'Track inventory must contain at least one record'
        }
        reference_doc = tracks_inventory.reference
        if (!(reference_doc instanceof Map) || !reference_doc.fasta || !reference_doc.manifest || !reference_doc.genome_id || !reference_doc.build) {
            error 'Track inventory reference requires fasta, manifest, genome_id, and build'
        }
        track_reference = file(resolve_track_inventory_location(tracks_inventory_file, reference_doc.fasta), checkIfExists: true)
        track_reference_manifest = file(resolve_track_inventory_location(tracks_inventory_file, reference_doc.manifest), checkIfExists: true)
        track_spec = [
            provider             : params.chipseq_track_provider,
            track_format         : params.chipseq_track_format,
            bin_size             : params.chipseq_track_bin_size as Integer,
            normalization        : params.chipseq_track_normalization,
            effective_genome_size: params.chipseq_track_effective_genome_size != null ? params.chipseq_track_effective_genome_size as Integer : null,
            scale_factor         : params.chipseq_track_scale_factor as Double,
            extend_reads         : params.chipseq_track_extend_reads.toString().toBoolean(),
            fragment_mode        : params.chipseq_track_fragment_mode,
            strand               : params.chipseq_track_strand,
            additional_filters   : params.chipseq_track_additional_filters,
        ]
        track_spec_base64 = groovy.json.JsonOutput.toJson(track_spec).getBytes('UTF-8').encodeBase64().toString()
        track_rows = tracks_inventory.records.collect { row ->
            def required = ['record_id', 'sample_id', 'dataset', 'condition', 'target', 'biological_replicate', 'technical_replicate', 'is_control', 'bam', 'bai', 'bam_manifest']
            def missing = required.findAll { field -> row[field] == null || row[field].toString().trim() == '' }
            if (missing) {
                error "Track inventory record is missing: ${missing.join(', ')}"
            }
            [
                record_id            : row.record_id.toString(), sample_id: row.sample_id.toString(),
                dataset              : row.dataset.toString(), condition: row.condition.toString(), target: row.target.toString(),
                biological_replicate : row.biological_replicate.toString(), technical_replicate: row.technical_replicate.toString(),
                is_control           : row.is_control.toString().toBoolean(),
                bam                  : file(resolve_track_inventory_location(tracks_inventory_file, row.bam), checkIfExists: true),
                bai                  : file(resolve_track_inventory_location(tracks_inventory_file, row.bai), checkIfExists: true),
                bam_manifest         : file(resolve_track_inventory_location(tracks_inventory_file, row.bam_manifest), checkIfExists: true),
            ]
        }
        record_ids = track_rows.collect { row -> row.record_id }
        if (record_ids.size() != record_ids.unique().size()) {
            error 'Track inventory record_id values must be unique'
        }
        track_tuples = track_rows.collect { row ->
            def meta = [
                id                    : "${row.record_id}.bigwig".replaceAll(/[^A-Za-z0-9._-]+/, '_'),
                track_role            : 'individual', record_id: row.record_id,
                record_ids            : [row.record_id], sample_ids: [row.sample_id],
                dataset               : row.dataset, condition: row.condition, target: row.target,
                is_control            : row.is_control,
                biological_replicates : [row.biological_replicate], technical_replicates: [row.technical_replicate],
                genome_id             : reference_doc.genome_id.toString(), build: reference_doc.build.toString(),
            ]
            tuple(meta, [row.bam], [row.bai], [row.bam_manifest], track_reference, track_reference_manifest, track_spec_base64)
        }
        if (params.chipseq_track_aggregate.toString().toBoolean()) {
            if (params.chipseq_track_aggregate_scope != 'condition_target') {
                error 'Native Track Generation v1 supports only chipseq_track_aggregate_scope=condition_target'
            }
            grouped_tracks = track_rows
                .findAll { row -> !row.is_control }
                .groupBy { row -> [row.dataset, row.condition, row.target] }
            grouped_tracks.each { group_key, rows ->
                rows = rows.sort { left, right -> left.record_id <=> right.record_id }
                def group_id = (["aggregate"] + group_key + [reference_doc.genome_id, reference_doc.build, 'bigwig'])
                    .collect { value -> value.toString().replaceAll(/[^A-Za-z0-9._-]+/, '_') }.join('.')
                def meta = [
                    id                    : group_id, track_role: 'aggregate', record_id: null,
                    record_ids            : rows.collect { row -> row.record_id },
                    sample_ids            : rows.collect { row -> row.sample_id },
                    dataset               : group_key[0], condition: group_key[1], target: group_key[2], is_control: false,
                    biological_replicates : rows.collect { row -> row.biological_replicate },
                    technical_replicates  : rows.collect { row -> row.technical_replicate },
                    genome_id             : reference_doc.genome_id.toString(), build: reference_doc.build.toString(),
                ]
                track_tuples << tuple(meta, rows.collect { row -> row.bam }, rows.collect { row -> row.bai }, rows.collect { row -> row.bam_manifest }, track_reference, track_reference_manifest, track_spec_base64)
            }
        }
        TRACK_GENERATION(channel.fromList(track_tuples))
        completed_ch = TRACK_GENERATION.out.status
        logs_ch = TRACK_GENERATION.out.reports
    } else if (run_mode == 'tracks') {
        no_dep = channel.value('none')
        CHIPSEQ_LEGACY_TRACKS(
            'chipseq', 'tracks', 'high_cpu', config_file, legacy_root,
            seed, no_dep, no_dep
        )
        completed_ch = CHIPSEQ_LEGACY_TRACKS.out.status
        logs_ch = CHIPSEQ_LEGACY_TRACKS.out.log
    } else if (run_mode == 'annotation' && native_annotation) {
        required_annotation_params = [
            chipseq_annotation_peaks            : params.chipseq_annotation_peaks,
            chipseq_annotation_peak_manifest    : params.chipseq_annotation_peak_manifest,
            chipseq_annotation_reference        : params.chipseq_annotation_reference,
            chipseq_annotation_reference_manifest: params.chipseq_annotation_reference_manifest,
            chipseq_annotation_gtf              : params.chipseq_annotation_gtf,
        ]
        missing_annotation_params = required_annotation_params.findAll { _key, value -> value == null || value.toString().trim() == '' }.keySet()
        if (missing_annotation_params) {
            error "Native annotation mode requires: ${missing_annotation_params.sort().join(', ')}"
        }
        peak_file = file(params.chipseq_annotation_peaks, checkIfExists: true)
        peak_manifest_file = file(params.chipseq_annotation_peak_manifest, checkIfExists: true)
        reference_file = file(params.chipseq_annotation_reference, checkIfExists: true)
        reference_manifest_file = file(params.chipseq_annotation_reference_manifest, checkIfExists: true)
        annotation_file = file(params.chipseq_annotation_gtf, checkIfExists: true)
        peak_document = new groovy.json.JsonSlurper().parse(peak_manifest_file.toFile())
        source_id = peak_document.id?.toString()
        if (!source_id) {
            error 'Peak annotation input manifest has no id'
        }
        annotation_id = "${source_id}.annotation".replaceAll(/[^A-Za-z0-9._-]+/, '_')
        annotation_meta = [
            id        : annotation_id,
            source_id : source_id,
            genome_id : peak_document.genome_id,
            organism  : peak_document.organism,
        ]
        annotation_spec = [
            provider            : params.chipseq_annotation_provider,
            mode                : params.chipseq_annotation_mode,
            overlap_mode        : params.chipseq_annotation_overlap_mode,
            promoter_upstream   : params.chipseq_annotation_promoter_upstream as Integer,
            promoter_downstream : params.chipseq_annotation_promoter_downstream as Integer,
            max_tss_distance    : params.chipseq_annotation_max_tss_distance,
            feature_priority    : params.chipseq_annotation_feature_priority.toString().split(',').collect { value -> value.trim() },
            gene_assignment     : params.chipseq_annotation_gene_assignment,
            strand_aware        : params.chipseq_annotation_strand_aware.toString().toBoolean(),
            intergenic_policy   : params.chipseq_annotation_intergenic_policy,
        ]
        annotation_spec_base64 = groovy.json.JsonOutput.toJson(annotation_spec).getBytes('UTF-8').encodeBase64().toString()
        annotation_inputs = channel.value(tuple(annotation_meta, peak_file, peak_manifest_file, reference_file, reference_manifest_file, annotation_file, annotation_spec_base64))
        PEAK_ANNOTATION(annotation_inputs)
        completed_ch = PEAK_ANNOTATION.out.status
        logs_ch = PEAK_ANNOTATION.out.reports
    } else if (run_mode == 'annotation') {
        no_dep = channel.value('none')
        CHIPSEQ_LEGACY_ANNOTATION(
            'chipseq', 'annotate', 'medium', config_file, legacy_root,
            seed, no_dep, no_dep
        )
        completed_ch = CHIPSEQ_LEGACY_ANNOTATION.out.status
        logs_ch = CHIPSEQ_LEGACY_ANNOTATION.out.log
    } else if (native_mode) {
        CHIPSEQ_NATIVE_FOUNDATION(config_file, legacy_root, seed)
        if (run_mode == 'post_alignment' && params.chipseq_continue_legacy_peaks) {
            no_dep = channel.value('none')
            CHIPSEQ_LEGACY_PEAKS(
                'chipseq', 'peaks', 'high_cpu', config_file, legacy_root,
                CHIPSEQ_NATIVE_FOUNDATION.out.completed.collect(), no_dep, no_dep
            )
            completed_ch = CHIPSEQ_LEGACY_PEAKS.out.status
            logs_ch = CHIPSEQ_NATIVE_FOUNDATION.out.logs.mix(CHIPSEQ_LEGACY_PEAKS.out.log)
        } else {
            completed_ch = CHIPSEQ_NATIVE_FOUNDATION.out.completed
            logs_ch = CHIPSEQ_NATIVE_FOUNDATION.out.logs
        }
    } else if (run_mode == 'consensus') {
        no_dep = channel.value('none')
        CHIPSEQ_LEGACY_CONSENSUS(
            'chipseq', 'consensus', 'high_cpu', config_file, legacy_root,
            seed, no_dep, no_dep
        )
        completed_ch = CHIPSEQ_LEGACY_CONSENSUS.out.status
        logs_ch = CHIPSEQ_LEGACY_CONSENSUS.out.log
    } else if (run_mode == 'idr') {
        error 'No scientifically equivalent legacy IDR provider exists; enable the native foundation, peak calling, Peak QC, and Consensus/IDR context'
    } else if (run_mode == 'differential_binding') {
        no_dep = channel.value('none')
        CHIPSEQ_LEGACY_DIFFERENTIAL(
            'chipseq', 'differential', 'high_memory', config_file, legacy_root,
            seed, no_dep, no_dep
        )
        completed_ch = CHIPSEQ_LEGACY_DIFFERENTIAL.out.status
        logs_ch = CHIPSEQ_LEGACY_DIFFERENTIAL.out.log
    } else if (run_mode in ['peaks', 'peak_qc'] && !native_peak_calling) {
        no_dep = channel.value('none')
        CHIPSEQ_LEGACY_PEAKS(
            'chipseq', 'peaks', 'high_cpu', config_file, legacy_root,
            seed, no_dep, no_dep
        )
        completed_ch = CHIPSEQ_LEGACY_PEAKS.out.status
        logs_ch = CHIPSEQ_LEGACY_PEAKS.out.log
    } else {
        CHIPSEQ_REFERENCE(config_file, legacy_root, seed)
        CHIPSEQ_QC_ALIGNMENT(config_file, legacy_root, CHIPSEQ_REFERENCE.out.status, seed)
        CHIPSEQ_PEAK_ANALYSIS(
            config_file,
            legacy_root,
            CHIPSEQ_REFERENCE.out.status,
            CHIPSEQ_QC_ALIGNMENT.out.filtered,
            CHIPSEQ_QC_ALIGNMENT.out.status
        )
        completed_ch = CHIPSEQ_PEAK_ANALYSIS.out.status
        logs_ch = CHIPSEQ_REFERENCE.out.logs
            .mix(CHIPSEQ_QC_ALIGNMENT.out.logs)
            .mix(CHIPSEQ_PEAK_ANALYSIS.out.logs)
    }

    emit:
    completed = completed_ch
    logs      = logs_ch
}
