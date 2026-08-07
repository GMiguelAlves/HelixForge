process MERGE_FASTQ {
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
    tuple val(meta), path(reads_r1), path(reads_r2)

    output:
    tuple val(meta), path("${meta.output_r1_name}"), path("${meta.output_r2_name}"), emit: artifacts
    tuple val(meta), path("${meta.id}.merge.tsv"), emit: reports
    tuple val(meta), path("${meta.id}.versions.yml"), emit: versions
    tuple val(meta), path("${meta.id}.merge.done"), emit: status

    script:
    def r1_list = reads_r1 instanceof List ? reads_r1 : [reads_r1]
    def r2_list = reads_r2 instanceof List ? reads_r2 : [reads_r2]
    def r1_args = r1_list.collect { read -> "'${read}'" }.join(' ')
    def r2_args = r2_list.collect { read -> "'${read}'" }.join(' ')
    def target_dir = meta.target_dir ?: ''
    """
    if [[ -n '${target_dir}' && -s '${meta.output_r1}' && -s '${meta.output_r2}' ]]; then
        cp '${meta.output_r1}' '${meta.output_r1_name}'
        cp '${meta.output_r2}' '${meta.output_r2_name}'
    else
        cat ${r1_args} > '${meta.output_r1_name}.tmp'
        cat ${r2_args} > '${meta.output_r2_name}.tmp'
        mv '${meta.output_r1_name}.tmp' '${meta.output_r1_name}'
        mv '${meta.output_r2_name}.tmp' '${meta.output_r2_name}'

        if [[ -n '${target_dir}' ]]; then
            mkdir -p '${target_dir}'
            cp '${meta.output_r1_name}' '${meta.output_r1}.nextflow.tmp'
            cp '${meta.output_r2_name}' '${meta.output_r2}.nextflow.tmp'
            mv '${meta.output_r1}.nextflow.tmp' '${meta.output_r1}'
            mv '${meta.output_r2}.nextflow.tmp' '${meta.output_r2}'
        fi
    fi

    {
        printf 'role\tpath\tsha256\n'
        sha256sum ${r1_args} | awk '{ print "input_r1\t" \$2 "\t" \$1 }'
        sha256sum ${r2_args} | awk '{ print "input_r2\t" \$2 "\t" \$1 }'
        sha256sum '${meta.output_r1_name}' | awk '{ print "output_r1\t" \$2 "\t" \$1 }'
        sha256sum '${meta.output_r2_name}' | awk '{ print "output_r2\t" \$2 "\t" \$1 }'
    } > '${meta.id}.merge.tsv'

    printf '"%s":\n    coreutils: %s\n' \
        '${task.process}' \
        "\$(cat --version | awk 'NR==1 { print \$NF }')" \
        > '${meta.id}.versions.yml'

    printf '{"id":"%s","process":"%s","status":"complete"}\n' \
        '${meta.id}' '${task.process}' > '${meta.id}.merge.done'
    """

    stub:
    """
    printf '@stub/1\nACGT\n+\nIIII\n' | gzip -c > '${meta.output_r1_name}'
    printf '@stub/2\nTGCA\n+\nIIII\n' | gzip -c > '${meta.output_r2_name}'
    printf 'role\tpath\tsha256\noutput_r1\t%s\tstub\noutput_r2\t%s\tstub\n' \
        '${meta.output_r1_name}' '${meta.output_r2_name}' > '${meta.id}.merge.tsv'
    printf '"MERGE_FASTQ":\n    coreutils: stub\n' > '${meta.id}.versions.yml'
    printf '{"id":"%s","process":"MERGE_FASTQ","status":"stub"}\n' \
        '${meta.id}' > '${meta.id}.merge.done'
    """
}
