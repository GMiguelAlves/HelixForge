nextflow.enable.dsl = 2

include { IMPORT } from '../../subworkflows/local/import/import'

workflow {
    provider = params.provider.toString().toLowerCase()
    if (!(provider in ['salmon', 'star'])) {
        error "provider must be salmon or star"
    }

    fixture_root = file(params.fixture_root, checkIfExists: true)
    metadata = file(params.metadata_file ?: "${fixture_root}/metadata.csv", checkIfExists: true)
    annotation = file("${fixture_root}/annotation.gtf", checkIfExists: true)
    target_root = params.target_root.toString()

    if (provider == 'salmon') {
        source_inputs = channel.of('sample_a', 'sample_b').map { sample ->
            def meta = [
                id        : "SYNTHETIC.${sample}.quantification",
                provider  : 'salmon',
                dataset   : 'SYNTHETIC',
                sample_id : sample,
                target_dir: "/legacy/quants/SYNTHETIC/${sample}"
            ]
            tuple(
                meta,
                file("${fixture_root}/salmon/${sample}/manifest.json", checkIfExists: true),
                file("${fixture_root}/salmon/${sample}/quant.sf", checkIfExists: true),
                'quantification'
            )
        }
        import_meta = [id: 'synthetic.import', provider: 'salmon', target_dir: target_root]
        import_params = [
            project            : '',
            allow_missing      : false,
            star_count_column  : 'unstranded',
            countsFromAbundance: 'no',
            libraryProtocol    : 'full_length',
            ignoreTxVersion    : true,
            ignoreAfterBar     : true,
            stripGeneVersion   : true,
            stripTranscriptPrefix: true,
            stripGenePrefix    : true,
            unmappedTranscripts: 'error'
        ]
        salmon_context = channel.of(tuple(import_meta, metadata, annotation, import_params))
        star_context = channel.empty()
    } else {
        source_inputs = channel.of('sample_a', 'sample_b').map { sample ->
            def meta = [
                id        : "SYNTHETIC.${sample}.alignment",
                provider  : 'star',
                dataset   : 'SYNTHETIC',
                sample_id : sample,
                target_dir: "/legacy/star/SYNTHETIC/${sample}"
            ]
            tuple(
                meta,
                file("${fixture_root}/star/${sample}/manifest.json", checkIfExists: true),
                file("${fixture_root}/star/${sample}/ReadsPerGene.out.tab", checkIfExists: true),
                'gene_counts'
            )
        }
        import_meta = [id: 'synthetic.import', provider: 'star', target_dir: target_root]
        import_params = [project: '', allow_missing: false, star_count_column: params.star_count_column, gene_id_normalization: 'legacy']
        salmon_context = channel.empty()
        star_context = channel.of(tuple(import_meta, metadata, import_params))
    }

    IMPORT(source_inputs, salmon_context, star_context)
}
