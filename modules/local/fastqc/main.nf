process FASTQC {
    tag "${meta.id}"
    label 'native_module'

    cpus 4
    memory 8.GB
    time 4.h
    cache 'deep'
    errorStrategy { task.exitStatus in 130..145 ? 'retry' : 'terminate' }
    maxRetries 2

    container params.fastqc_container
    conda "${moduleDir}/environment.yml"

    publishDir "${params.outdir}/pipeline_info/native_qc/fastqc",
        mode: 'copy', overwrite: true,
        pattern: '*.{html,log,yml,done}'

    input:
    tuple val(meta), path(input_artifact)

    output:
    tuple val(meta), path("${prefix}_fastqc.zip"), emit: artifacts
    tuple val(meta), path("${prefix}_fastqc.html"), path("${meta.id}.fastqc.log"), emit: reports
    tuple val(meta), path("${meta.id}.versions.yml"), emit: versions
    tuple val(meta), path("${meta.id}.fastqc.done"), emit: status

    script:
    prefix = input_artifact.name.replaceFirst(/\.(fastq|fq)(\.gz)?$/, '')
    def html_name = "${prefix}_fastqc.html"
    def zip_name = "${prefix}_fastqc.zip"
    def target_dir = meta.target_dir ?: ''
    """
    if [[ -n '${target_dir}' && -s '${target_dir}/${html_name}' && -s '${target_dir}/${zip_name}' ]]; then
        echo '[SKIP] FastQC ja existe: ${meta.id}' | tee '${meta.id}.fastqc.log'
        cp '${target_dir}/${html_name}' '${html_name}'
        cp '${target_dir}/${zip_name}' '${zip_name}'
    else
        fastqc '${input_artifact}' \
            --outdir . \
            --threads ${task.cpus} \
            2>&1 | tee '${meta.id}.fastqc.log'

        [[ -s '${html_name}' && -s '${zip_name}' ]]

        if [[ -n '${target_dir}' ]]; then
            mkdir -p '${target_dir}'
            cp '${html_name}' '${target_dir}/${html_name}.nextflow.tmp'
            cp '${zip_name}' '${target_dir}/${zip_name}.nextflow.tmp'
            mv '${target_dir}/${html_name}.nextflow.tmp' '${target_dir}/${html_name}'
            mv '${target_dir}/${zip_name}.nextflow.tmp' '${target_dir}/${zip_name}'
        fi
    fi

    printf '"%s":\n    fastqc: %s\n' \
        '${task.process}' \
        "\$(fastqc --version 2>&1 | awk 'NF { print \$NF; exit }' | sed 's/^v//')" \
        > '${meta.id}.versions.yml'

    printf '{"id":"%s","process":"%s","status":"complete"}\n' \
        '${meta.id}' '${task.process}' > '${meta.id}.fastqc.done'
    """

    stub:
    prefix = input_artifact.name.replaceFirst(/\.(fastq|fq)(\.gz)?$/, '')
    """
    printf 'PK\003\004stub-fastqc\n' > '${prefix}_fastqc.zip'
    printf '<!doctype html><html><body>stub FastQC %s</body></html>\n' \
        '${meta.id}' > '${prefix}_fastqc.html'
    printf '[STUB] FastQC %s\n' '${meta.id}' > '${meta.id}.fastqc.log'
    printf '"FASTQC":\n    fastqc: stub\n' > '${meta.id}.versions.yml'
    printf '{"id":"%s","process":"FASTQC","status":"stub"}\n' \
        '${meta.id}' > '${meta.id}.fastqc.done'
    """
}
