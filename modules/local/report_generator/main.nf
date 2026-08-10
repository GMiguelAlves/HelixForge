process REPORT_GENERATOR {
    tag "${meta.id}"
    label 'native_module'
    label 'report_low'

    cpus 1
    memory 1.GB
    time 20.m
    cache 'deep'
    errorStrategy 'terminate'
    maxRetries 0

    container params.chipseq_report_container
    conda "${moduleDir}/environment.yml"

    publishDir "${params.outdir}/chipseq/report",
        mode: 'copy', overwrite: true, pattern: 'report_result'
    publishDir "${params.outdir}/pipeline_info/native_chipseq/report/generator",
        mode: 'copy', overwrite: true, pattern: '*.{json,yml,done,log}'

    input:
    tuple val(meta), path(aggregate_dir), val(presentation_base64)

    output:
    tuple val(meta), path('report_result'), emit: artifacts
    tuple val(meta), path("${meta.id}.report_generator.execution.json"), path("${meta.id}.report_generator.log"), emit: reports
    tuple val(meta), path("${meta.id}.report_generator.versions.yml"), emit: versions
    tuple val(meta), path("${meta.id}.report_generator.done"), emit: status

    script:
    """
    generate_chipseq_report.py \
        --aggregate-dir '${aggregate_dir}' \
        --presentation-base64 '${presentation_base64}' \
        --output-dir report_result \
        --execution '${meta.id}.report_generator.execution.json' \
        --versions '${meta.id}.report_generator.versions.yml' \
        --cpus ${task.cpus} \
        --memory-bytes ${task.memory.toBytes()} \
        --task-time '${task.time}' \
        2>&1 | tee '${meta.id}.report_generator.log'
    printf '{"id":"%s","process":"REPORT_GENERATOR","status":"complete"}\n' '${meta.id}' \
        > '${meta.id}.report_generator.done'
    """

    stub:
    """
    mkdir -p report_result
    printf '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>ChIP-seq report</title><style>body{font-family:sans-serif}</style></head><body><h1>ChIP-seq report</h1><section><h2>Consensus / IDR</h2><p>not_implemented</p></section></body></html>\n' > report_result/chipseq_report.html
    cp '${aggregate_dir}/report_data.json' report_result/report.json
    cp '${aggregate_dir}/provenance.json' report_result/provenance.json
    cp '${aggregate_dir}/versions.yml' report_result/versions.yml
    printf '{"schema_version":"1.0","id":"%s","process":"REPORT_GENERATOR","status":"stub"}\n' '${meta.id}' > report_result/execution.json
    printf '{"schema_version":"1.0","type":"chipseq_report","id":"%s","provider":"html_v1","artifacts":{"report":{"path":"chipseq_report.html"},"structured_json":{"path":"report.json"}},"status":"incomplete"}\n' '${meta.id}' > report_result/manifest.json
    cp report_result/execution.json '${meta.id}.report_generator.execution.json'
    printf '"REPORT_GENERATOR":\n    python: stub\n' > '${meta.id}.report_generator.versions.yml'
    printf '[STUB] Report generator\n' > '${meta.id}.report_generator.log'
    printf '{"id":"%s","process":"REPORT_GENERATOR","status":"stub"}\n' '${meta.id}' > '${meta.id}.report_generator.done'
    """
}
