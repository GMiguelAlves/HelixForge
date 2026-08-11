nextflow.enable.dsl = 2

include { FASTQC } from '../../modules/local/fastqc/main'

workflow {
    read = file(params.read, checkIfExists: true)
    FASTQC(channel.of(tuple([
        id        : 'TEST.fastqc.real.R1',
        dataset   : 'TEST',
        sample_id : 'sample',
        phase     : 'raw',
        target_dir: params.target_dir.toString()
    ], read)))
}
