nextflow.enable.dsl = 2

include { CONSENSUS_IDR } from '../../subworkflows/local/chipseq/consensus'

workflow {
    fixture = file(params.fixture_dir, checkIfExists: true)
    plan = file("${fixture}/peak_plan.tsv", checkIfExists: true)
    records = ['chip_rep1', 'chip_rep2']
    peak_artifacts = channel.fromList(records).map { record_id ->
        def peak_id = "${record_id}.H3K27ac.narrow.macs3"
        tuple([id: peak_id], file("${fixture}/${peak_id}.peak_calling", checkIfExists: true))
    }
    peak_manifests = channel.fromList(records).map { record_id ->
        def peak_id = "${record_id}.H3K27ac.narrow.macs3"
        tuple([id: peak_id], file("${fixture}/${peak_id}.peak.manifest.json", checkIfExists: true))
    }
    qc_manifests = channel.fromList(records).map { record_id ->
        def peak_id = "${record_id}.H3K27ac.narrow.macs3"
        tuple([id: peak_id], file("${fixture}/${peak_id}.qc.manifest.json", checkIfExists: true))
    }
    peak_plan = channel.of(tuple([id: 'fixture.peak-context'], plan, plan))
    strategy = params.chipseq_run_mode == 'idr' ? 'idr' : params.chipseq_consensus_method
    spec = [
        strategy: strategy, min_replicates: params.chipseq_min_replicates,
        replicate_mode: 'biological', replicate_policy: 'require_premerged',
        require_same_caller: true, idr_threshold: 0.05, rank_metric: 'signal_value'
    ]
    spec_base64 = groovy.json.JsonOutput.toJson(spec).getBytes('UTF-8').encodeBase64().toString()
    CONSENSUS_IDR(peak_artifacts, peak_manifests, qc_manifests, peak_plan, channel.value(spec_base64))
}
