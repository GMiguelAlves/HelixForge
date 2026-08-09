include { IMPORT_SOURCE }                              from '../../../modules/local/import_source/main'
include { IMPORT_SAMPLE_TABLE as SALMON_SAMPLE_TABLE } from '../../../modules/local/import_sample_table/main'
include { IMPORT_SAMPLE_TABLE as STAR_SAMPLE_TABLE }   from '../../../modules/local/import_sample_table/main'
include { TX2GENE_BUILD }                              from '../../../modules/local/tx2gene_build/main'
include { TXIMPORT as SALMON_IMPORT }                  from '../../../modules/local/tximport/main'
include { STAR_IMPORT }                                from '../../../modules/local/star_import/main'

workflow IMPORT {
    take:
    source_inputs
    salmon_context
    star_context

    main:
    IMPORT_SOURCE(source_inputs)

    salmon_sources = IMPORT_SOURCE.out.artifacts
        .filter { meta, _source -> meta.provider == 'salmon' }
        .map { _meta, source -> source }
        .collect()
    star_sources = IMPORT_SOURCE.out.artifacts
        .filter { meta, _source -> meta.provider == 'star' }
        .map { _meta, source -> source }
        .collect()

    salmon_sample_context = salmon_context.map { meta, metadata, _annotation, import_params ->
        tuple(meta, metadata, import_params)
    }
    star_sample_context = star_context.map { meta, metadata, import_params ->
        tuple(meta, metadata, import_params)
    }
    SALMON_SAMPLE_TABLE(salmon_sample_context, salmon_sources)
    STAR_SAMPLE_TABLE(star_sample_context, star_sources)

    tx2gene_inputs = salmon_context.map { meta, _metadata, annotation, import_params ->
        def tx_meta = meta + [id: "${meta.id}.tx2gene"]
        tuple(tx_meta, annotation, [
            strip_transcript_version: import_params.ignoreTxVersion,
            strip_gene_version      : import_params.stripGeneVersion,
            strip_transcript_prefix : import_params.stripTranscriptPrefix,
            strip_gene_prefix       : import_params.stripGenePrefix
        ])
    }
    TX2GENE_BUILD(tx2gene_inputs)

    SALMON_IMPORT(SALMON_SAMPLE_TABLE.out.artifacts, TX2GENE_BUILD.out.artifacts, salmon_sources)
    STAR_IMPORT(STAR_SAMPLE_TABLE.out.artifacts, star_sources)

    emit:
    counts             = SALMON_IMPORT.out.counts.mix(STAR_IMPORT.out.counts)
    abundance          = SALMON_IMPORT.out.abundance.mix(STAR_IMPORT.out.abundance)
    lengths            = SALMON_IMPORT.out.lengths
    experiment         = SALMON_IMPORT.out.experiment
    metadata           = SALMON_IMPORT.out.metadata.mix(STAR_IMPORT.out.metadata)
    versions           = IMPORT_SOURCE.out.versions
        .mix(SALMON_SAMPLE_TABLE.out.versions)
        .mix(STAR_SAMPLE_TABLE.out.versions)
        .mix(TX2GENE_BUILD.out.versions)
        .mix(SALMON_IMPORT.out.versions)
        .mix(STAR_IMPORT.out.versions)
    execution_metadata = SALMON_IMPORT.out.execution_metadata.mix(STAR_IMPORT.out.execution_metadata)
    manifest           = SALMON_IMPORT.out.manifest.mix(STAR_IMPORT.out.manifest)
    status             = SALMON_IMPORT.out.status.mix(STAR_IMPORT.out.status)
    reports            = IMPORT_SOURCE.out.reports
        .mix(SALMON_SAMPLE_TABLE.out.reports)
        .mix(STAR_SAMPLE_TABLE.out.reports)
        .mix(TX2GENE_BUILD.out.reports)
        .mix(SALMON_IMPORT.out.reports)
        .mix(STAR_IMPORT.out.reports)
}
