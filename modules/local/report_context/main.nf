process REPORT_CONTEXT {
    tag "${meta.id}"
    label 'native_module'
    label 'report_low'

    cpus 1
    memory 1.GB
    time 15.m
    cache 'deep'
    errorStrategy 'terminate'
    maxRetries 0

    container params.chipseq_report_container
    conda "${moduleDir}/environment.yml"

    publishDir "${params.outdir}/pipeline_info/native_chipseq/report/context",
        mode: 'copy', overwrite: true, pattern: '*.{json,yml,done,log}'

    input:
    tuple val(meta), path(inventory), path(manifests, stageAs: 'manifests??/*')

    output:
    tuple val(meta), path("${meta.id}.report_context.json"), emit: artifacts
    tuple val(meta), path("${meta.id}.report_context.log"), emit: reports
    tuple val(meta), path("${meta.id}.report_context.versions.yml"), emit: versions
    tuple val(meta), path("${meta.id}.report_context.done"), emit: status

    script:
    def manifestArgs = manifests.collect { value -> "--manifest '${value}'" }.join(' ')
    """
    validate_report_context.py \
        --inventory '${inventory}' \
        ${manifestArgs} \
        --output '${meta.id}.report_context.json' \
        2>&1 | tee '${meta.id}.report_context.log'
    printf '"REPORT_CONTEXT":\n    python: "%s"\n' "\$(python3 --version | awk '{print \$2}')" \
        > '${meta.id}.report_context.versions.yml'
    printf '{"id":"%s","process":"REPORT_CONTEXT","status":"complete"}\n' '${meta.id}' \
        > '${meta.id}.report_context.done'
    """

    stub:
    """
    printf '{"schema_version":"1.0","type":"chipseq_report_context","id":"%s","project":{"project_id":"stub","dataset":"stub","genome_id":"stub_v1","build":"stub_v1"},"required_components":[],"components":{"metadata":{"status":"not_requested","manifests":[]},"reference":{"status":"not_requested","manifests":[]},"alignment":{"status":"not_requested","manifests":[]},"bam":{"status":"incomplete","manifests":[{"type":"bam_final","id":"stub_bam","sha256":"stub","status":"stub"}]},"peak":{"status":"not_requested","manifests":[]},"peak_qc":{"status":"not_requested","manifests":[]},"consensus_idr":{"status":"not_implemented","manifests":[{"type":"idr","id":"stub_idr","sha256":"stub","status":"not_implemented"}]},"differential_binding":{"status":"not_requested","manifests":[]},"annotation":{"status":"not_requested","manifests":[]},"tracks":{"status":"not_requested","manifests":[]},"provenance":{"status":"not_requested","manifests":[]}},"records":[],"versions":{},"status":"incomplete"}\n' '${meta.id}' > '${meta.id}.report_context.json'
    printf '[STUB] Report context\n' > '${meta.id}.report_context.log'
    printf '"REPORT_CONTEXT":\n    python: stub\n' > '${meta.id}.report_context.versions.yml'
    printf '{"id":"%s","process":"REPORT_CONTEXT","status":"stub"}\n' '${meta.id}' > '${meta.id}.report_context.done'
    """
}
