process TRIM_GALORE_SINGLE {
    tag "${meta.id}"
    label 'native_module'
    cpus 8
    memory 24.GB
    time 8.h
    cache 'deep'
    container params.trim_galore_container
    conda "${moduleDir}/../trim_galore/environment.yml"

    input:
    tuple val(meta), path(raw_r1)

    output:
    tuple val(meta), path("${meta.trimmed_r1_name}"), emit: artifacts
    tuple val(meta), path("${meta.id}.trim_galore_reports"), emit: reports
    tuple val(meta), path("${meta.id}.versions.yml"), emit: versions
    tuple val(meta), path("${meta.id}.trim_galore.done"), emit: status

    script:
    def generated = raw_r1.name.replaceFirst(/\.(fastq|fq)(\.gz)?$/, '') + '_trimmed.fq.gz'
    """
    mkdir -p '${meta.id}.trim_galore_reports' '${meta.trimmed_dir}'
    trim_galore --gzip --quality '${meta.trim_quality}' --length '${meta.trim_length}' \
        --cores ${task.cpus} --output_dir . '${raw_r1}' \
        2>&1 | tee '${meta.id}.trim_galore_reports/trim_galore.log'
    [[ -s '${generated}' ]]
    mv '${generated}' '${meta.trimmed_r1_name}'
    cp '${meta.trimmed_r1_name}' '${meta.trimmed_r1}.nextflow.tmp'
    mv '${meta.trimmed_r1}.nextflow.tmp' '${meta.trimmed_r1}'
    printf '"%s":\n    trim_galore: "%s"\n' '${task.process}' \
        "\$(trim_galore --version 2>&1 | awk 'tolower(\$1)=="version" {print \$2; exit}')" \
        > '${meta.id}.versions.yml'
    printf '{"id":"%s","process":"%s","status":"complete","library_layout":"single"}\n' \
        '${meta.id}' '${task.process}' > '${meta.id}.trim_galore.done'
    """

    stub:
    """
    printf '@stub\nACGT\n+\nIIII\n' | gzip -c > '${meta.trimmed_r1_name}'
    mkdir -p '${meta.id}.trim_galore_reports' '${meta.trimmed_dir}'
    cp '${meta.trimmed_r1_name}' '${meta.trimmed_r1}'
    printf '[STUB] single-end trim\n' > '${meta.id}.trim_galore_reports/trim_galore.log'
    printf '"TRIM_GALORE_SINGLE":\n    trim_galore: stub\n' > '${meta.id}.versions.yml'
    printf '{"id":"%s","status":"stub","library_layout":"single"}\n' '${meta.id}' > '${meta.id}.trim_galore.done'
    """
}
