process MERGE_FASTQ_SINGLE {
    tag "${meta.id}"
    label 'native_module'
    cpus 2
    memory 16.GB
    time 6.h
    cache 'deep'
    errorStrategy { task.exitStatus in 130..145 ? 'retry' : 'terminate' }
    maxRetries 2
    container params.merge_fastq_container
    conda "${moduleDir}/environment.yml"

    publishDir "${params.outdir}/pipeline_info/native_qc/merge_fastq",
        mode: 'copy', overwrite: true,
        pattern: '*.{tsv,yml,done}'

    input:
    tuple val(meta), path(reads_r1)

    output:
    tuple val(meta), path("${meta.output_r1_name}"), emit: artifacts
    tuple val(meta), path("${meta.id}.merge.tsv"), emit: reports
    tuple val(meta), path("${meta.id}.versions.yml"), emit: versions
    tuple val(meta), path("${meta.id}.merge.done"), emit: status

    script:
    def r1_list = reads_r1 instanceof List ? reads_r1 : [reads_r1]
    def r1_args = r1_list.collect { read -> "'${read}'" }.join(' ')
    """
    cat ${r1_args} > '${meta.output_r1_name}.tmp'
    mv '${meta.output_r1_name}.tmp' '${meta.output_r1_name}'
    mkdir -p '${meta.target_dir}'
    cp '${meta.output_r1_name}' '${meta.output_r1}.nextflow.tmp'
    mv '${meta.output_r1}.nextflow.tmp' '${meta.output_r1}'
    {
        printf 'role\tpath\tsha256\n'
        sha256sum ${r1_args} | awk '{ print "input_r1\t" \$2 "\t" \$1 }'
        sha256sum '${meta.output_r1_name}' | awk '{ print "output_r1\t" \$2 "\t" \$1 }'
    } > '${meta.id}.merge.tsv'
    printf '"MERGE_FASTQ_SINGLE":\n    coreutils: "%s"\n' \
        "\$(cat --version | awk 'NR==1 {print \$NF}')" > '${meta.id}.versions.yml'
    printf '{"id":"%s","process":"%s","status":"complete","library_layout":"single"}\n' \
        '${meta.id}' '${task.process}' > '${meta.id}.merge.done'
    """

    stub:
    """
    printf '@stub\nACGT\n+\nIIII\n' | gzip -c > '${meta.output_r1_name}'
    mkdir -p '${meta.target_dir}'
    cp '${meta.output_r1_name}' '${meta.output_r1}'
    printf 'role\tpath\tsha256\noutput_r1\t%s\tstub\n' '${meta.output_r1_name}' > '${meta.id}.merge.tsv'
    printf '"MERGE_FASTQ_SINGLE":\n    coreutils: stub\n' > '${meta.id}.versions.yml'
    printf '{"id":"%s","process":"MERGE_FASTQ_SINGLE","status":"stub","library_layout":"single"}\n' '${meta.id}' > '${meta.id}.merge.done'
    """
}
