process REPORT_AGGREGATE {
    tag "${meta.id}"
    label 'native_module'
    label 'report_low'

    cpus 1
    memory 2.GB
    time 30.m
    cache 'deep'
    errorStrategy 'terminate'
    maxRetries 0

    container { workflow.containerEngine in ['singularity', 'apptainer'] ? params.chipseq_report_apptainer_container : params.chipseq_report_container }
    conda "${moduleDir}/environment.yml"

    publishDir "${params.outdir}/pipeline_info/native_chipseq/report/aggregate",
        mode: 'copy', overwrite: true, pattern: '*.{json,yml,done,log}'

    input:
    tuple val(meta), path(context), path(manifests, stageAs: 'manifests??/*'), path(semantic_artifacts, stageAs: 'artifacts??/*', arity: '0..*')

    output:
    tuple val(meta), path('report_aggregate'), emit: artifacts
    tuple val(meta), path("${meta.id}.report_aggregate.execution.json"), path("${meta.id}.report_aggregate.log"), emit: reports
    tuple val(meta), path("${meta.id}.report_aggregate.versions.yml"), emit: versions
    tuple val(meta), path("${meta.id}.report_aggregate.done"), emit: status

    script:
    def manifestArgs = manifests.collect { value -> "--manifest '${value}'" }.join(' ')
    def artifactArgs = semantic_artifacts.collect { value -> "--artifact '${value}'" }.join(' ')
    """
    set -o pipefail
    report_aggregate.py \
        --context '${context}' \
        ${manifestArgs} \
        ${artifactArgs} \
        --output-dir report_aggregate \
        --execution '${meta.id}.report_aggregate.execution.json' \
        --versions '${meta.id}.report_aggregate.versions.yml' \
        --cpus ${task.cpus} \
        --memory-bytes ${task.memory.toBytes()} \
        --task-time '${task.time}' \
        2>&1 | tee '${meta.id}.report_aggregate.log'
    printf '{"id":"%s","process":"REPORT_AGGREGATE","status":"complete"}\n' '${meta.id}' \
        > '${meta.id}.report_aggregate.done'
    """

    stub:
    """
    mkdir -p report_aggregate
    printf '{"schema_version":"1.0","type":"chipseq_report_data","id":"%s","project":{"project_id":"stub","dataset":"stub","genome_id":"stub_v1","build":"stub_v1"},"sections":{"project":{"status":"available","data":{}},"reference":{"status":"not_requested","data":null},"sequencing_qc":{"status":"not_requested","data":null},"alignment":{"status":"not_requested","data":null},"bam_processing":{"status":"incomplete","data":{"records":[]}},"peak_calling":{"status":"not_requested","data":null},"peak_qc":{"status":"not_requested","data":null},"consensus_idr":{"status":"not_implemented","data":{"idr_status":"not_implemented"}},"differential_binding":{"status":"not_requested","data":null},"annotation":{"status":"not_requested","data":null},"tracks":{"status":"not_requested","data":null},"provenance":{"status":"available","data":{}}},"status":"incomplete"}\n' '${meta.id}' > report_aggregate/report_data.json
    printf 'component\tstatus\nconsensus_idr\tnot_implemented\n' > report_aggregate/components.tsv
    printf 'record_id\tsample_id\n' > report_aggregate/records.tsv
    printf '{"schema_version":"1.0","type":"chipseq_report_aggregate","id":"%s","artifacts":{"report_data":{"path":"report_data.json"}},"status":"incomplete"}\n' '${meta.id}' > report_aggregate/manifest.json
    printf '{"sources":[],"status":"stub"}\n' > report_aggregate/provenance.json
    printf '"REPORT_AGGREGATE":\n    python: stub\n' > report_aggregate/versions.yml
    printf '{"id":"%s","process":"REPORT_AGGREGATE","status":"stub"}\n' '${meta.id}' > '${meta.id}.report_aggregate.execution.json'
    cp report_aggregate/versions.yml '${meta.id}.report_aggregate.versions.yml'
    printf '[STUB] Report aggregate\n' > '${meta.id}.report_aggregate.log'
    printf '{"id":"%s","process":"REPORT_AGGREGATE","status":"stub"}\n' '${meta.id}' > '${meta.id}.report_aggregate.done'
    """
}
