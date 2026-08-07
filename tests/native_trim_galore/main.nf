nextflow.enable.dsl = 2

include { TRIM_GALORE } from '../../modules/local/trim_galore/main'

workflow {
    def target_dir = file(params.target_dir)
    def meta = [
        dataset        : 'SYNTHETIC',
        sample_id      : 'synthetic_sample',
        run_accession  : 'synthetic_run',
        trim_quality   : params.trim_quality,
        trim_length    : params.trim_length,
        trimmed_r1     : "${target_dir}/synthetic_R1_trimmed.fastq.gz",
        trimmed_r2     : "${target_dir}/synthetic_R2_trimmed.fastq.gz",
        trimmed_dir    : target_dir.toString(),
        trimmed_r1_name: 'synthetic_R1_trimmed.fastq.gz',
        trimmed_r2_name: 'synthetic_R2_trimmed.fastq.gz'
    ]

    input_reads = channel.of(
        tuple(
            meta,
            file(params.read1, checkIfExists: true),
            file(params.read2, checkIfExists: true)
        )
    )

    TRIM_GALORE(input_reads)
}
