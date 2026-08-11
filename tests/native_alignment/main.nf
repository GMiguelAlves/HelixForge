nextflow.enable.dsl = 2

include { REFERENCE_INDEX } from '../../subworkflows/local/alignment/reference_index'
include { ALIGNMENT }       from '../../subworkflows/local/alignment/alignment'

workflow {
    aligner = (params.aligner ?: 'star').toString().toLowerCase()
    if (!(aligner in ['star', 'bowtie2'])) {
        error 'aligner must be star or bowtie2'
    }
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
                id        : "synthetic.${aligner}.index",
                aligner   : aligner,
                target_dir: "${target_root}/${aligner}_index"
            ],
            reference,
            annotation,
            aligner == 'star' ? [
                genome_sa_index_nbases   : params.genome_sa_index_nbases,
                limit_genome_generate_ram: params.limit_genome_generate_ram
            ] : [basename: 'genome', extra_args: params.index_extra_args ?: '']
        )
    )
    REFERENCE_INDEX(index_inputs)

    if (!params.index_only) {
        alignment_inputs = REFERENCE_INDEX.out.artifacts.map { _index_meta, index ->
            tuple(
                [
                    id        : "SYNTHETIC.synthetic_sample.${aligner}.alignment",
                    aligner   : aligner,
                    dataset   : 'SYNTHETIC',
                    sample_id : 'synthetic_sample',
                    single_end: false,
                    target_dir: "${target_root}/${aligner}_output"
                ],
                reads,
                reference,
                annotation,
                index,
                aligner == 'star' ? [
                    read_files_command: 'zcat',
                    extra_args        : params.extra_args
                ] : [index_basename: 'genome', extra_args: params.bowtie2_extra_args ?: '']
            )
        }
        ALIGNMENT(alignment_inputs)
    }
}
