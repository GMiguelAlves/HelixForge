nextflow.enable.dsl = 2

include { TRACK_GENERATION } from '../../subworkflows/local/chipseq/tracks'

workflow {
    fixture = file(params.fixture_dir, checkIfExists: true)
    spec = [
        provider: 'deeptools_bamcoverage_v1', track_format: 'bigwig', bin_size: 10,
        normalization: 'CPM', effective_genome_size: null, scale_factor: 1.0,
        extend_reads: false, fragment_mode: 'reads', strand: 'unstranded',
        additional_filters: 'none'
    ]
    spec_base64 = groovy.json.JsonOutput.toJson(spec).getBytes('UTF-8').encodeBase64().toString()
    reference = file("${fixture}/reference.fa", checkIfExists: true)
    reference_manifest = file("${fixture}/reference_manifest.json", checkIfExists: true)
    rows = ['input_rep1', 'chip_rep1', 'chip_rep2'].collect { record_id ->
        [
            record_id: record_id, sample_id: record_id,
            condition: record_id == 'input_rep1' ? 'control' : 'treated',
            target: record_id == 'input_rep1' ? 'input' : 'H3K27ac',
            is_control: record_id == 'input_rep1',
            biological_replicate: record_id.endsWith('2') ? '2' : '1',
            bam: file("${fixture}/${record_id}.filtered.bam", checkIfExists: true),
            bai: file("${fixture}/${record_id}.filtered.bam.bai", checkIfExists: true),
            manifest: file("${fixture}/${record_id}.manifest.json", checkIfExists: true)
        ]
    }
    requests = rows.collect { row ->
        def meta = [
            id: "${row.record_id}.bigwig", track_role: 'individual', record_id: row.record_id,
            record_ids: [row.record_id], sample_ids: [row.sample_id], dataset: 'stub',
            condition: row.condition, target: row.target, is_control: row.is_control,
            biological_replicates: [row.biological_replicate], technical_replicates: ['1'],
            genome_id: 'stub_v1', build: 'stub_v1'
        ]
        tuple(meta, [row.bam], [row.bai], [row.manifest], reference, reference_manifest, spec_base64)
    }
    chips = rows.findAll { row -> !row.is_control }
    aggregate_meta = [
        id: 'aggregate.stub.treated.H3K27ac.stub_v1.stub_v1.bigwig', track_role: 'aggregate', record_id: null,
        record_ids: chips.collect { row -> row.record_id }, sample_ids: chips.collect { row -> row.sample_id },
        dataset: 'stub', condition: 'treated', target: 'H3K27ac', is_control: false,
        biological_replicates: chips.collect { row -> row.biological_replicate }, technical_replicates: ['1', '1'],
        genome_id: 'stub_v1', build: 'stub_v1'
    ]
    requests << tuple(aggregate_meta, chips.collect { row -> row.bam }, chips.collect { row -> row.bai }, chips.collect { row -> row.manifest }, reference, reference_manifest, spec_base64)
    TRACK_GENERATION(channel.fromList(requests))
}
