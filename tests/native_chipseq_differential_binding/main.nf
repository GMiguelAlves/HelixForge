nextflow.enable.dsl = 2

include { DIFFERENTIAL_BINDING } from '../../subworkflows/local/chipseq/differential_binding'

workflow {
    fixture = file(params.fixture_dir, checkIfExists: true)
    conditions = ['control', 'treated']
    records = conditions.collectMany { condition -> [1, 2].collect { replicate -> "${condition}_rep${replicate}" } }
    consensus_artifacts = channel.fromList(conditions).map { condition ->
        tuple([id: "fixture.${condition}"], file("${fixture}/fixture.${condition}.consensus_result", checkIfExists: true))
    }
    consensus_manifests = channel.fromList(conditions).map { condition ->
        tuple([id: "fixture.${condition}"], file("${fixture}/fixture.${condition}.manifest.json", checkIfExists: true))
    }
    final_bams = channel.fromList(records).map { record_id ->
        tuple([id: record_id], file("${fixture}/${record_id}.filtered.bam", checkIfExists: true),
              file("${fixture}/${record_id}.filtered.bam.bai", checkIfExists: true))
    }
    bam_manifests = channel.fromList(records).map { record_id ->
        tuple([id: record_id], file("${fixture}/${record_id}.bam.manifest.json", checkIfExists: true))
    }
    plan = file("${fixture}/peak_plan.tsv", checkIfExists: true)
    peak_plan = channel.of(tuple([id: 'fixture.peak-context'], plan, plan))
    db_spec = channel.value(file("${fixture}/db_spec.json", checkIfExists: true))
    DIFFERENTIAL_BINDING(consensus_artifacts, consensus_manifests, final_bams, bam_manifests, peak_plan, db_spec)
}
