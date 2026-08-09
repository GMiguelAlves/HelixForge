nextflow.enable.dsl = 2

include { PEAK_QC } from '../../subworkflows/local/chipseq/peak_qc'

workflow {
    fixture = file(params.fixture_dir, checkIfExists: true)
    peak_plan = file("${fixture}/peak_plan.tsv", checkIfExists: true)
    records = ['chip_rep1', 'chip_rep2']

    final_bams = channel.fromList(records).map { record_id ->
        tuple(
            [
                id: record_id, sample_id: record_id, dataset: 'fixture', target: 'H3K27ac',
                single_end: false, bam_duplicate_policy: 'remove', bam_min_mapq: 30,
                bam_include_flags: 0, bam_exclude_flags: 2308, bam_blacklist_policy: 'fragment'
            ],
            file("${fixture}/${record_id}.filtered.bam", checkIfExists: true),
            file("${fixture}/${record_id}.filtered.bam.bai", checkIfExists: true)
        )
    }
    final_manifests = channel.fromList(records).map { record_id ->
        tuple([id: record_id], file("${fixture}/${record_id}.bam.manifest.json", checkIfExists: true))
    }
    peak_artifacts = channel.fromList(records).map { record_id ->
        def peak_id = "${record_id}.H3K27ac.narrow.macs3"
        tuple([id: peak_id], file("${fixture}/${peak_id}.peak_calling", checkIfExists: true))
    }
    peak_manifests = channel.fromList(records).map { record_id ->
        def peak_id = "${record_id}.H3K27ac.narrow.macs3"
        tuple([id: peak_id], file("${fixture}/${peak_id}.manifest.json", checkIfExists: true))
    }
    peak_plan_channel = channel.of(tuple([id: 'fixture.peak-context'], peak_plan, peak_plan))
    spec = [
        unit: 'layout', min_mapq: 0, include_flags: 0, additional_exclude_flags: 0,
        exclude_unmapped: true, exclude_secondary: true, exclude_supplementary: true,
        exclude_qc_fail: true, duplicate_handling: 'include', require_proper_pair: true,
        overlap_strategy: 'any_base', blacklist_policy: 'bam_preprocessed'
    ]
    spec_base64 = groovy.json.JsonOutput.toJson(spec).getBytes('UTF-8').encodeBase64().toString()
    PEAK_QC(final_bams, final_manifests, peak_artifacts, peak_manifests, peak_plan_channel, channel.value(spec_base64))
}
