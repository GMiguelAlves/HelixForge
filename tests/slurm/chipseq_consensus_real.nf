nextflow.enable.dsl = 2

include { CONSENSUS_IDR } from '../../subworkflows/local/chipseq/consensus'

workflow {
    peaks_root = file(params.peaks_dir, checkIfExists: true)
    qc_root = file(params.peak_qc_dir, checkIfExists: true)
    plan = file(params.peak_plan, checkIfExists: true)
    records = ['chip_rep1', 'chip_rep2']

    peak_artifacts = channel.fromList(records).map { record_id ->
        def peak_id = "${record_id}.H3K27ac.narrow.macs3"
        tuple([id: peak_id], file("${peaks_root}/${peak_id}.peak_calling", checkIfExists: true))
    }
    peak_manifests = channel.fromList(records).map { record_id ->
        def peak_id = "${record_id}.H3K27ac.narrow.macs3"
        tuple([id: peak_id], file("${peaks_root}/${peak_id}.peak_calling/manifest.json", checkIfExists: true))
    }
    qc_manifests = channel.fromList(records).map { record_id ->
        def peak_id = "${record_id}.H3K27ac.narrow.macs3"
        tuple([id: peak_id], file("${qc_root}/pipeline_info/native_chipseq/peak_qc/frip/${peak_id}.frip.manifest.json", checkIfExists: true))
    }
    peak_plan = channel.of(tuple([id: 'fixture.peak-context'], plan, plan))
    spec = [
        strategy: 'union', min_replicates: 2,
        replicate_mode: 'biological', replicate_policy: 'require_premerged',
        require_same_caller: true, idr_threshold: 0.05, rank_metric: 'signal_value'
    ]
    spec_base64 = groovy.json.JsonOutput.toJson(spec).getBytes('UTF-8').encodeBase64().toString()
    CONSENSUS_IDR(peak_artifacts, peak_manifests, qc_manifests,
        peak_plan, channel.value(spec_base64))
}

