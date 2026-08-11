nextflow.enable.dsl = 2

include { PEAK_QC } from '../../subworkflows/local/chipseq/peak_qc'

workflow {
    bam_fixture = file(params.bam_fixture_dir, checkIfExists: true)
    peaks_root = file(params.peaks_dir, checkIfExists: true)
    plan = file(params.peak_plan, checkIfExists: true)
    records = ['chip_rep1', 'chip_rep2']

    final_bams = channel.fromList(records).map { record_id ->
        tuple(
            [
                id: record_id, sample_id: record_id, dataset: 'fixture', target: 'H3K27ac',
                single_end: false, bam_duplicate_policy: 'all', bam_min_mapq: 0,
                bam_include_flags: 0, bam_exclude_flags: 0, bam_blacklist_policy: 'none'
            ],
            file("${bam_fixture}/${record_id}.filtered.bam", checkIfExists: true),
            file("${bam_fixture}/${record_id}.filtered.bam.bai", checkIfExists: true)
        )
    }
    final_manifests = channel.fromList(records).map { record_id ->
        tuple([id: record_id], file("${bam_fixture}/${record_id}.manifest.json", checkIfExists: true))
    }
    peak_artifacts = channel.fromList(records).map { record_id ->
        def peak_id = "${record_id}.H3K27ac.narrow.macs3"
        tuple([id: peak_id], file("${peaks_root}/${peak_id}.peak_calling", checkIfExists: true))
    }
    peak_manifests = channel.fromList(records).map { record_id ->
        def peak_id = "${record_id}.H3K27ac.narrow.macs3"
        tuple([id: peak_id], file("${peaks_root}/${peak_id}.peak_calling/manifest.json", checkIfExists: true))
    }
    peak_plan_channel = channel.of(tuple([id: 'fixture.peak-context'], plan, plan))
    spec = [
        unit: 'layout', min_mapq: 0, include_flags: 0, additional_exclude_flags: 0,
        exclude_unmapped: true, exclude_secondary: true, exclude_supplementary: true,
        exclude_qc_fail: true, duplicate_handling: 'include', require_proper_pair: true,
        overlap_strategy: 'any_base', blacklist_policy: 'none'
    ]
    spec_base64 = groovy.json.JsonOutput.toJson(spec).getBytes('UTF-8').encodeBase64().toString()
    PEAK_QC(final_bams, final_manifests, peak_artifacts, peak_manifests,
        peak_plan_channel, channel.value(spec_base64))
}

