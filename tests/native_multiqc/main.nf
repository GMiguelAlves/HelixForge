nextflow.enable.dsl = 2

include { MULTIQC } from '../../modules/local/multiqc/main'

workflow {
    input_dir = file(params.input_dir, checkIfExists: true)
    target_root = file(params.target_root)
    inputs = [
        file("${input_dir}/sample_a_fastqc", checkIfExists: true),
        file("${input_dir}/sample_b_fastqc", checkIfExists: true)
    ]

    requests = channel.of(
        tuple(
            [
                id         : 'certification.multiqc',
                dataset    : 'certification',
                report_name: 'certification_multiqc.html',
                target_dir : target_root.toString()
            ],
            inputs
        )
    )

    MULTIQC(requests)
}
