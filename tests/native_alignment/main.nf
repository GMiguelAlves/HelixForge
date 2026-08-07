nextflow.enable.dsl = 2

include { REFERENCE_INDEX } from '../../subworkflows/local/alignment/reference_index'
include { ALIGNMENT }       from '../../subworkflows/local/alignment/alignment'

workflow {
    reference = file(params.reference, checkIfExists: true)
    annotation = file(params.annotation, checkIfExists: true)
    reads = [
        file(params.read1, checkIfExists: true),
        file(params.read2, checkIfExists: true)
    ]
    target_root = params.target_root.toString()

    index_inputs = channel.of(
        tuple(
            [
                id        : 'synthetic.star.index',
                aligner   : 'star',
                target_dir: "${target_root}/star_index"
            ],
            reference,
            annotation,
            [
                genome_sa_index_nbases   : params.genome_sa_index_nbases,
                limit_genome_generate_ram: params.limit_genome_generate_ram
            ]
        )
    )
    REFERENCE_INDEX(index_inputs)

    if (!params.index_only) {
        alignment_inputs = REFERENCE_INDEX.out.artifacts.map { _index_meta, index ->
            tuple(
                [
                    id        : 'SYNTHETIC.synthetic_sample.alignment',
                    aligner   : 'star',
                    dataset   : 'SYNTHETIC',
                    sample_id : 'synthetic_sample',
                    single_end: false,
                    target_dir: "${target_root}/star_output"
                ],
                reads,
                reference,
                annotation,
                index,
                [
                    read_files_command: 'zcat',
                    extra_args        : params.extra_args
                ]
            )
        }
        ALIGNMENT(alignment_inputs)
    }
}
