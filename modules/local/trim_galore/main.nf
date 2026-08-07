process TRIM_GALORE {
    tag "${meta.id}"
    label 'native_module'

    cpus 8
    memory 24.GB
    time 8.h
    cache 'deep'
    errorStrategy { task.exitStatus in 130..145 ? 'retry' : 'terminate' }
    maxRetries 2

    container params.trim_galore_container
    conda "${moduleDir}/environment.yml"

    publishDir "${params.outdir}/pipeline_info/native_qc/trim_galore",
        mode: 'copy', overwrite: true,
        pattern: '*.{done,yml}'

    input:
    tuple val(meta), path(raw_r1), path(raw_r2)

    output:
    tuple val(meta), path("${meta.trimmed_r1_name}"), path("${meta.trimmed_r2_name}"), emit: artifacts
    tuple val(meta), path("${meta.id}.trim_galore_reports"), emit: reports
    tuple val(meta), path("${meta.id}.versions.yml"), emit: versions
    tuple val(meta), path("${meta.id}.trim_galore.done"), emit: status

    script:
    def generated_r1 = raw_r1.name.replaceFirst(/\.fastq\.gz$/, '') + '_val_1.fq.gz'
    def generated_r2 = raw_r2.name.replaceFirst(/\.fastq\.gz$/, '') + '_val_2.fq.gz'
    def report_r1 = raw_r1.name + '_trimming_report.txt'
    def report_r2 = raw_r2.name + '_trimming_report.txt'
    """
    mkdir -p '${meta.id}.trim_galore_reports'

    if [[ -s '${meta.trimmed_r1}' && -s '${meta.trimmed_r2}' ]]; then
        echo '[SKIP] Trimmed run ja existe: ${meta.run_accession}' \
            | tee '${meta.id}.trim_galore.log'
        cp '${meta.trimmed_r1}' '${meta.trimmed_r1_name}'
        cp '${meta.trimmed_r2}' '${meta.trimmed_r2_name}'
        for report in '${report_r1}' '${report_r2}'; do
            if [[ -s '${meta.trimmed_dir}'/"\$report" ]]; then
                cp '${meta.trimmed_dir}'/"\$report" "\$report"
            fi
        done
    else
        trim_galore --paired \
            --quality '${meta.trim_quality}' \
            --length '${meta.trim_length}' \
            --cores ${task.cpus} \
            --output_dir . \
            '${raw_r1}' '${raw_r2}' \
            2>&1 | tee '${meta.id}.trim_galore.log'

        [[ -s '${generated_r1}' && -s '${generated_r2}' ]]
        mv '${generated_r1}' '${meta.trimmed_r1_name}'
        mv '${generated_r2}' '${meta.trimmed_r2_name}'

        mkdir -p '${meta.trimmed_dir}'
        cp '${meta.trimmed_r1_name}' '${meta.trimmed_r1}.nextflow.tmp'
        cp '${meta.trimmed_r2_name}' '${meta.trimmed_r2}.nextflow.tmp'
        mv '${meta.trimmed_r1}.nextflow.tmp' '${meta.trimmed_r1}'
        mv '${meta.trimmed_r2}.nextflow.tmp' '${meta.trimmed_r2}'

        for report in '${report_r1}' '${report_r2}'; do
            if [[ -s "\$report" ]]; then
                cp "\$report" "${meta.trimmed_dir}/\${report}.nextflow.tmp"
                mv "${meta.trimmed_dir}/\${report}.nextflow.tmp" \
                    "${meta.trimmed_dir}/\${report}"
            fi
        done
    fi

    cp '${meta.id}.trim_galore.log' '${meta.id}.trim_galore_reports/'
    for report in '${report_r1}' '${report_r2}'; do
        if [[ -s "\$report" ]]; then
            cp "\$report" '${meta.id}.trim_galore_reports/'
        fi
    done

    printf '"%s":\n    trim_galore: %s\n    cutadapt: %s\n' \
        '${task.process}' \
        "\$(trim_galore --version 2>&1 | awk 'NF { print \$NF; exit }')" \
        "\$(cutadapt --version 2>&1 | awk 'NF { print \$NF; exit }')" \
        > '${meta.id}.versions.yml'

    printf '{"id":"%s","process":"%s","status":"complete"}\n' \
        '${meta.id}' '${task.process}' > '${meta.id}.trim_galore.done'
    """

    stub:
    """
    printf '@stub/1\nACGT\n+\nIIII\n' | gzip -c > '${meta.trimmed_r1_name}'
    printf '@stub/2\nTGCA\n+\nIIII\n' | gzip -c > '${meta.trimmed_r2_name}'
    mkdir -p '${meta.id}.trim_galore_reports'
    printf '[STUB] Trim Galore %s/%s\n' \
        '${meta.dataset}' '${meta.run_accession}' > '${meta.id}.trim_galore_reports/${meta.id}.trim_galore.log'
    printf '[STUB] trimming report R1\n' > '${meta.id}.trim_galore_reports/${raw_r1.name}_trimming_report.txt'
    printf '[STUB] trimming report R2\n' > '${meta.id}.trim_galore_reports/${raw_r2.name}_trimming_report.txt'
    printf 'TRIM_GALORE:\n    trim_galore: stub\n    cutadapt: stub\n' \
        > '${meta.id}.versions.yml'
    printf '{"id":"%s","process":"TRIM_GALORE","status":"stub"}\n' \
        '${meta.id}' > '${meta.id}.trim_galore.done'
    """
}
