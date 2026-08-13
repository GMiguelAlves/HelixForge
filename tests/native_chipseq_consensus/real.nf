nextflow.enable.dsl = 2

include { IDR_PROVIDER } from '../../modules/local/idr_provider/main'

workflow {
    fixture = file(params.fixture_dir, checkIfExists: true)
    request = file("${fixture}/idr_request.json", checkIfExists: true)
    peak_dirs = [
        file("${fixture}/chip_rep1.H3K27ac.narrow.macs3.peak_calling", checkIfExists: true),
        file("${fixture}/chip_rep2.H3K27ac.narrow.macs3.peak_calling", checkIfExists: true),
    ]
    meta = [
        id: 'fixture.fixture.H3K27ac.treated.H3K27ac.fixture_v1.narrow',
        dataset: 'fixture', condition: 'treated', target: 'H3K27ac',
        genome_id: 'fixture_v1', strategy: 'idr',
    ]
    IDR_PROVIDER(channel.value(tuple(meta, peak_dirs, request)))
}
