process BOWTIE2_INDEX {
    tag "${meta.id}"
    label 'native_module'
    label 'alignment_index'

    cpus 8
    memory 32.GB
    time 12.h
    queue { params.bowtie2_index_queue ?: null }
    cache 'deep'
    errorStrategy { task.exitStatus in 130..145 ? 'retry' : 'terminate' }
    maxRetries 2

    container "${workflow.containerEngine in ['singularity', 'apptainer'] ? params.bowtie2_apptainer_container : params.bowtie2_container}"
    conda "${moduleDir}/environment.yml"

    publishDir "${params.outdir}/pipeline_info/native_alignment/bowtie2_index",
        mode: 'copy', overwrite: true,
        pattern: '*.{json,yml,done,bowtie2_index_reports}'
    publishDir { meta.target_dir ?: "${params.outdir}/alignment_index/${meta.id}" },
        mode: 'copy', overwrite: true,
        pattern: 'bowtie2_index/*',
        saveAs: { filename -> filename.replaceFirst('^bowtie2_index/', '') }

    input:
    tuple val(meta), path(reference), path(annotation), val(index_params)

    output:
    tuple val(meta), path('bowtie2_index'), emit: artifacts
    tuple val(meta), path("${meta.id}.bowtie2_index_reports"), emit: reports
    tuple val(meta), path("${meta.id}.versions.yml"), emit: versions
    tuple val(meta), path("${meta.id}.execution.json"), emit: execution_metadata
    tuple val(meta), path("${meta.id}.manifest.json"), emit: manifest
    tuple val(meta), path("${meta.id}.bowtie2_index.done"), emit: status

    script:
    def extra_args = index_params.extra_args ?: ''
    def basename = index_params.basename ?: 'genome'
    """
    set -o pipefail
    start_epoch=\$(date +%s)
    mkdir -p bowtie2_index '${meta.id}.bowtie2_index_reports'

    if [[ '${extra_args}' =~ (^|[[:space:]])(--threads|-p)([[:space:]]|=|\$) ]]; then
        echo '[ERROR] Bowtie2 index options override threads controlled by the API.' >&2
        exit 2
    fi

    CMD=(bowtie2-build --threads ${task.cpus})
    if [[ -n '${extra_args}' ]]; then
        EXTRA_ARGS=(${extra_args})
        CMD+=("\${EXTRA_ARGS[@]}")
    fi
    CMD+=('${reference}' 'bowtie2_index/${basename}')
    printf '%q ' "\${CMD[@]}" > '${meta.id}.bowtie2_index_reports/command.txt'
    printf '\n' >> '${meta.id}.bowtie2_index_reports/command.txt'
    "\${CMD[@]}" 2>&1 | tee '${meta.id}.bowtie2_index_reports/bowtie2_build.log'

    shopt -s nullglob
    index_files=(bowtie2_index/${basename}.*.bt2 bowtie2_index/${basename}.*.bt2l)
    (( \${#index_files[@]} >= 6 )) || { echo '[ERROR] incomplete Bowtie2 index' >&2; exit 3; }

    reference_sha=\$(sha256sum '${reference}' | awk '{print \$1}')
    index_sha=\$(find bowtie2_index -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum | awk '{print \$1}')
    end_epoch=\$(date +%s)
    printf 'reference\tsha256\n%s\t%s\nindex\t%s\n' '${reference}' "\$reference_sha" "\$index_sha" \
        > '${meta.id}.bowtie2_index_reports/checksums.tsv'
    printf '"%s":\n    bowtie2: %s\n' '${task.process}' \
        "\$(bowtie2-build --version 2>&1 | sed -n '1s/.*version //p')" > '${meta.id}.versions.yml'
    printf '{"id":"%s","process":"%s","cpus":%s,"memory_bytes":%s,"time":"%s","reference_sha256":"%s","index_sha256":"%s","started_epoch":%s,"ended_epoch":%s,"elapsed_seconds":%s}\n' \
        '${meta.id}' '${task.process}' '${task.cpus}' '${task.memory.toBytes()}' '${task.time}' \
        "\$reference_sha" "\$index_sha" "\$start_epoch" "\$end_epoch" "\$((end_epoch-start_epoch))" \
        > '${meta.id}.execution.json'
    printf '{"schema_version":"1.1","type":"alignment_index","id":"%s","aligner":"bowtie2","basename":"%s","artifact":"bowtie2_index","sha256":"%s","reference_sha256":"%s"}\n' \
        '${meta.id}' '${basename}' "\$index_sha" "\$reference_sha" > '${meta.id}.manifest.json'
    printf '{"id":"%s","process":"%s","status":"complete"}\n' '${meta.id}' '${task.process}' \
        > '${meta.id}.bowtie2_index.done'
    """

    stub:
    def basename = index_params.basename ?: 'genome'
    """
    mkdir -p bowtie2_index '${meta.id}.bowtie2_index_reports'
    for suffix in 1 2 3 4; do printf 'stub\n' > 'bowtie2_index/${basename}'."\$suffix".bt2; done
    for suffix in 1 2; do printf 'stub\n' > 'bowtie2_index/${basename}'.rev."\$suffix".bt2; done
    printf 'bowtie2-build [stub]\n' > '${meta.id}.bowtie2_index_reports/command.txt'
    printf '[STUB] Bowtie2 index\n' > '${meta.id}.bowtie2_index_reports/bowtie2_build.log'
    printf 'reference\tsha256\nindex\tstub\n' > '${meta.id}.bowtie2_index_reports/checksums.tsv'
    printf '"BOWTIE2_INDEX":\n    bowtie2: stub\n' > '${meta.id}.versions.yml'
    printf '{"id":"%s","process":"BOWTIE2_INDEX","status":"stub"}\n' '${meta.id}' > '${meta.id}.execution.json'
    printf '{"schema_version":"1.1","type":"alignment_index","id":"%s","aligner":"bowtie2","basename":"%s","sha256":"stub"}\n' '${meta.id}' '${basename}' > '${meta.id}.manifest.json'
    printf '{"id":"%s","process":"BOWTIE2_INDEX","status":"stub"}\n' '${meta.id}' > '${meta.id}.bowtie2_index.done'
    """
}

