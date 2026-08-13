process CHIPSEQ_FULL_REPORT_INPUT {
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

    publishDir "${params.outdir}/pipeline_info/native_chipseq/full",
        mode: 'copy', overwrite: true, pattern: '*.{json,yml,done,log}'

    input:
    tuple val(meta), path(manifests, stageAs: 'manifests??/*'), path(semantic_artifacts, stageAs: 'artifacts??/*', arity: '0..*')

    output:
    tuple val(meta), path('chipseq_full_report_input.json'), emit: artifacts
    tuple val(meta), path('chipseq_full_report_input.log'), emit: reports
    tuple val(meta), path('chipseq_full_report_input.versions.yml'), emit: versions
    tuple val(meta), path('chipseq_full_report_input.done'), emit: status

    script:
    def manifestArgs = manifests.collect { value -> "--manifest '${value}'" }.join(' ')
    def artifactArgs = semantic_artifacts.collect { value -> "--artifact '${value}'" }.join(' ')
    """
    set -o pipefail
    python '${moduleDir}/resources/usr/bin/build_chipseq_full_report_input.py' \
        --meta-base64 '${groovy.json.JsonOutput.toJson(meta).getBytes('UTF-8').encodeBase64().toString()}' \
        ${manifestArgs} \
        ${artifactArgs} \
        --output chipseq_full_report_input.json \
        2>&1 | tee chipseq_full_report_input.log
    printf '"CHIPSEQ_FULL_REPORT_INPUT":\n    python: %s\n' "\$(python3 --version | awk '{print \$2}')" > chipseq_full_report_input.versions.yml
    printf '{"id":"%s","process":"CHIPSEQ_FULL_REPORT_INPUT","status":"complete"}\n' '${meta.id}' > chipseq_full_report_input.done
    """

    stub:
    """
    printf '{"schema_version":"1.0","type":"chipseq_report_input","project":{"project_id":"%s","dataset":"%s","genome_id":"%s","build":"%s"},"required_components":[],"components":[]}\n' \
        '${meta.project_id}' '${meta.dataset}' '${meta.genome_id}' '${meta.build}' > chipseq_full_report_input.json
    printf '[STUB] Full ChIP-seq report input\n' > chipseq_full_report_input.log
    printf '"CHIPSEQ_FULL_REPORT_INPUT":\n    python: stub\n' > chipseq_full_report_input.versions.yml
    printf '{"id":"%s","process":"CHIPSEQ_FULL_REPORT_INPUT","status":"stub"}\n' '${meta.id}' > chipseq_full_report_input.done
    """
}
