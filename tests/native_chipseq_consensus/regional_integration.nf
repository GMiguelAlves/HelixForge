nextflow.enable.dsl = 2
include { CONSENSUS_IDR } from '../../subworkflows/local/chipseq/consensus'

workflow {
    root = file(params.case_root, checkIfExists: true)
    ids = ['ip1', 'ip2', 'ip3']
    artifacts = channel.fromList(ids).map { id -> tuple([id: id], file("${root}/${id}.peak_calling", checkIfExists: true)) }
    manifests = channel.fromList(ids).map { id -> tuple([id: id], file("${root}/${id}.peak_calling/manifest.json", checkIfExists: true)) }
    qc = channel.fromList(ids).map { id -> tuple([id: id], file("${root}/${id}.peak_calling/qc.json", checkIfExists: true)) }
    plan = file(params.peak_plan, checkIfExists: true)
    spec = [strategy: 'regional_catalog', min_replicates: 2, replicate_mode: 'biological', replicate_policy: 'require_premerged', require_same_caller: true]
    encoded = groovy.json.JsonOutput.toJson(spec).getBytes('UTF-8').encodeBase64().toString()
    CONSENSUS_IDR(artifacts, manifests, qc, channel.of(tuple([id: 'plan'], plan, plan)), channel.value(encoded))
}
