include { CONSENSUS_IDR } from '../../subworkflows/local/chipseq/consensus'
include { PEAK_ANNOTATION } from '../../subworkflows/local/chipseq/peak_annotation'

workflow {
    fixture = file(params.fixture_dir, checkIfExists: true)
    records = new groovy.json.JsonSlurper().parse(file("${fixture}/records.json").toFile())
    artifacts = channel.fromList(records).map { row -> tuple([id: row.peak_id], file("${fixture}/${row.peak_directory}")) }
    manifests = channel.fromList(records).map { row -> tuple([id: row.peak_id], file("${fixture}/${row.record_id}.peak.json")) }
    qc = channel.fromList(records).map { row -> tuple([id: row.peak_id], file("${fixture}/${row.record_id}.qc.json")) }
    plan = file("${fixture}/plan.tsv")
    spec = groovy.json.JsonOutput.toJson([strategy: 'nfcore_2_1', min_replicates: 2,
        replicate_mode: 'biological', replicate_policy: 'require_premerged', require_same_caller: true]).bytes.encodeBase64().toString()
    CONSENSUS_IDR(artifacts, manifests, qc, channel.of(tuple([id: 'fixture.plan'], plan, plan)), channel.value(spec))
    annotationSpec = groovy.json.JsonOutput.toJson([provider: 'homer_4_11', mode: 'homer_native']).bytes.encodeBase64().toString()
    annotation = CONSENSUS_IDR.out.artifacts.map { meta, directory -> tuple(meta.id, meta, directory) }
        .join(CONSENSUS_IDR.out.provider_manifests.map { meta, manifest -> tuple(meta.id, manifest) })
        .map { _id, meta, directory, manifest -> tuple(meta + [id: "${meta.id}.annotation", source_id: meta.id],
            file("${directory}/consolidated_peaks.bed"), manifest, file("${fixture}/reference.fa"),
            file("${fixture}/reference.json"), file("${fixture}/annotation.gtf"), annotationSpec, [directory]) }
    PEAK_ANNOTATION(annotation)
}
