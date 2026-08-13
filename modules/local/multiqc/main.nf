process MULTIQC {
    tag "${meta.id}"
    label 'native_module'

    cpus 2
    memory 8.GB
    time 2.h
    cache 'deep'
    errorStrategy { task.exitStatus in 130..145 ? 'retry' : 'terminate' }
    maxRetries 2

    container params.multiqc_container
    conda "${moduleDir}/environment.yml"

    publishDir "${params.outdir}/pipeline_info/native_qc/multiqc",
        mode: 'copy', overwrite: true,
        pattern: '*.{html,log,yml,done}'
    publishDir { meta.target_dir ?: "${params.outdir}/pipeline_info/native_qc/multiqc/results" },
        mode: 'copy', overwrite: true,
        saveAs: { name ->
            def dataName = meta.report_name.replaceFirst(/\.html$/, '') + '_data'
            name == meta.report_name || name == dataName ? name : null
        }

    input:
    tuple val(meta), path(qc_inputs)

    output:
    tuple val(meta), path("${report_data_dir}"), emit: artifacts
    tuple val(meta), path("${meta.report_name}"), path("${meta.id}.multiqc.log"), emit: reports
    tuple val(meta), path("${meta.id}.versions.yml"), emit: versions
    tuple val(meta), path("${meta.id}.multiqc.done"), emit: status

    script:
    report_data_dir = meta.report_name.replaceFirst(/\.html$/, '') + '_data'
    def inputs = qc_inputs instanceof List ? qc_inputs : [qc_inputs]
    def input_args = inputs.collect { artifact -> "'${artifact}'" }.join(' ')
    """
    multiqc ${input_args} \
        -o . \
        -n '${meta.report_name}' \
        2>&1 | tee '${meta.id}.multiqc.log'

    [[ -s '${meta.report_name}' && -d '${report_data_dir}' ]]

    printf '"%s":\n    multiqc: %s\n' \
        '${task.process}' \
        "\$(multiqc --version 2>&1 | awk 'NF { print \$NF; exit }')" \
        > '${meta.id}.versions.yml'

    printf '{"id":"%s","process":"%s","status":"complete"}\n' \
        '${meta.id}' '${task.process}' > '${meta.id}.multiqc.done'
    """

    stub:
    report_data_dir = meta.report_name.replaceFirst(/\.html$/, '') + '_data'
    """
    mkdir -p '${report_data_dir}'
    printf '<!doctype html><html><body>stub MultiQC %s</body></html>\n' \
        '${meta.id}' > '${meta.report_name}'
    printf 'Sample\tmetric\n%s\tstub\n' '${meta.id}' \
        > '${report_data_dir}/multiqc_data.txt'
    printf '[STUB] MultiQC %s\n' '${meta.id}' > '${meta.id}.multiqc.log'
    printf '"MULTIQC":\n    multiqc: stub\n' > '${meta.id}.versions.yml'
    printf '{"id":"%s","process":"MULTIQC","status":"stub"}\n' \
        '${meta.id}' > '${meta.id}.multiqc.done'
    """
}
