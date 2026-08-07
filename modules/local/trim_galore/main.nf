process TRIM_GALORE {
    tag "${meta.dataset}:${meta.sample_id}:${meta.run_accession}"
    label 'native_trim_galore'

    cpus 8
    memory 24.GB
    time 8.h
    cache 'deep'
    errorStrategy { task.exitStatus in 130..145 ? 'retry' : 'terminate' }
    maxRetries 2

    container params.trim_galore_container
    conda "${moduleDir}/environment.yml"

    publishDir "${params.outdir}/pipeline_info/native_trim_galore",
        mode: 'copy', overwrite: true,
        pattern: '*.{done,log,yml}'

    input:
    tuple val(meta), path(raw_r1), path(raw_r2)

    output:
    tuple val(meta), path("${meta.trimmed_r1_name}"), path("${meta.trimmed_r2_name}"), emit: reads
    tuple val(meta), path("${meta.run_accession}.trim_galore.done"), emit: status
    path "${meta.run_accession}.trim_galore.log", emit: log
    path "${meta.run_accession}.versions.yml", emit: versions

    script:
    def generated_r1 = raw_r1.name.replaceFirst(/\.fastq\.gz$/, '') + '_val_1.fq.gz'
    def generated_r2 = raw_r2.name.replaceFirst(/\.fastq\.gz$/, '') + '_val_2.fq.gz'
    def report_r1 = raw_r1.name + '_trimming_report.txt'
    def report_r2 = raw_r2.name + '_trimming_report.txt'
    """
    if [[ -s '${meta.trimmed_r1}' && -s '${meta.trimmed_r2}' ]]; then
        echo '[SKIP] Trimmed run ja existe: ${meta.run_accession}' \
            | tee '${meta.run_accession}.trim_galore.log'
        cp '${meta.trimmed_r1}' '${meta.trimmed_r1_name}'
        cp '${meta.trimmed_r2}' '${meta.trimmed_r2_name}'
    else
        trim_galore --paired \
            --quality '${meta.trim_quality}' \
            --length '${meta.trim_length}' \
            --cores ${task.cpus} \
            --output_dir . \
            '${raw_r1}' '${raw_r2}' \
            2>&1 | tee '${meta.run_accession}.trim_galore.log'

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

    printf '"%s":\n    trim_galore: %s\n    cutadapt: %s\n' \
        '${task.process}' \
        "\$(trim_galore --version 2>&1 | awk 'NF { print \$NF; exit }')" \
        "\$(cutadapt --version 2>&1 | awk 'NF { print \$NF; exit }')" \
        > '${meta.run_accession}.versions.yml'

    printf '{"dataset":"%s","sample_id":"%s","run_accession":"%s","status":"complete"}\n' \
        '${meta.dataset}' '${meta.sample_id}' '${meta.run_accession}' \
        > '${meta.run_accession}.trim_galore.done'
    """

    stub:
    """
    printf '@stub/1\nACGT\n+\nIIII\n' | gzip -c > '${meta.trimmed_r1_name}'
    printf '@stub/2\nTGCA\n+\nIIII\n' | gzip -c > '${meta.trimmed_r2_name}'
    printf '[STUB] Trim Galore %s/%s\n' \
        '${meta.dataset}' '${meta.run_accession}' > '${meta.run_accession}.trim_galore.log'
    printf 'TRIM_GALORE:\n    trim_galore: stub\n    cutadapt: stub\n' \
        > '${meta.run_accession}.versions.yml'
    printf '{"dataset":"%s","sample_id":"%s","run_accession":"%s","status":"stub"}\n' \
        '${meta.dataset}' '${meta.sample_id}' '${meta.run_accession}' \
        > '${meta.run_accession}.trim_galore.done'
    """
}
