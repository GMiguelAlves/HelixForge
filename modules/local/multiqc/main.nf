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
    def target_dir = meta.target_dir ?: ''
    """
    if [[ -n '${target_dir}' && -s '${target_dir}/${meta.report_name}' && -d '${target_dir}/${report_data_dir}' ]]; then
        echo '[SKIP] MultiQC ja existe: ${meta.id}' | tee '${meta.id}.multiqc.log'
        cp '${target_dir}/${meta.report_name}' '${meta.report_name}'
        cp -a '${target_dir}/${report_data_dir}' '${report_data_dir}'
    else
        multiqc ${input_args} \
            -o . \
            -n '${meta.report_name}' \
            2>&1 | tee '${meta.id}.multiqc.log'

        [[ -s '${meta.report_name}' && -d '${report_data_dir}' ]]

        if [[ -n '${target_dir}' ]]; then
            mkdir -p '${target_dir}'
            cp '${meta.report_name}' '${target_dir}/${meta.report_name}.nextflow.tmp'
            cp -a '${report_data_dir}' '${target_dir}/${report_data_dir}.nextflow.tmp'
            mv '${target_dir}/${meta.report_name}.nextflow.tmp' '${target_dir}/${meta.report_name}'
            mv '${target_dir}/${report_data_dir}.nextflow.tmp' '${target_dir}/${report_data_dir}'
        fi
    fi

    printf '"%s":\n    multiqc: %s\n' \
        '${task.process}' \
        "\$(multiqc --version 2>&1 | awk 'NF { print \$NF; exit }')" \
        > '${meta.id}.versions.yml'

    printf '{"id":"%s","process":"%s","status":"complete"}\n' \
        '${meta.id}' '${task.process}' > '${meta.id}.multiqc.done'
    """

    stub:
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
