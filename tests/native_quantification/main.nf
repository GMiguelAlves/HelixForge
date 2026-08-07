nextflow.enable.dsl = 2

include { TRANSCRIPTOME_INDEX } from '../../subworkflows/local/quantification/transcriptome_index'
include { QUANTIFICATION }      from '../../subworkflows/local/quantification/quantification'

workflow {
    transcriptome = file(params.transcriptome, checkIfExists: true)
    reads = [
        file(params.read1, checkIfExists: true),
        file(params.read2, checkIfExists: true)
    ]
    target_root = params.target_root.toString()

    index_inputs = channel.of(
        tuple(
            [
                id        : 'synthetic.salmon.index',
                quantifier: 'salmon',
                index_key : "${target_root}/salmon_index",
                target_dir: "${target_root}/salmon_index"
            ],
            transcriptome,
            [kmer_size: params.kmer_size]
        )
    )
    TRANSCRIPTOME_INDEX(index_inputs)

    if (!params.index_only) {
        quantification_inputs = TRANSCRIPTOME_INDEX.out.artifacts.map { _index_meta, index ->
            tuple(
                [
                    id        : 'SYNTHETIC.synthetic_sample.quantification',
                    quantifier: 'salmon',
                    dataset   : 'SYNTHETIC',
                    sample_id : 'synthetic_sample',
                    single_end: false,
                    target_dir: "${target_root}/quants/SYNTHETIC/synthetic_sample"
                ],
                reads,
                transcriptome,
                index,
                [
                    lib_type         : params.lib_type,
                    validate_mappings: params.validate_mappings
                ]
            )
        }
        QUANTIFICATION(quantification_inputs)
    }
}
