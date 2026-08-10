process SALMON_QUANT {
    tag "${meta.id}"
    label 'native_module'
    label 'quantification_high'

    cpus 8
    memory 32.GB
    time 12.h
    queue { params.salmon_quant_queue ?: null }
    cache 'deep'
    errorStrategy { task.exitStatus in 130..145 ? 'retry' : 'terminate' }
    maxRetries 2

    container "${workflow.containerEngine in ['singularity', 'apptainer'] ? params.salmon_apptainer_container : params.salmon_container}"
    conda "${moduleDir}/environment.yml"

    publishDir "${params.outdir}/pipeline_info/native_quantification/salmon_quant",
        mode: 'copy', overwrite: true,
        pattern: '*.{json,yml,done,quantification_logs,quantification_statistics}'
    publishDir { meta.target_dir ?: "${params.outdir}/quantification/${meta.id}" },
        mode: 'copy', overwrite: true,
        pattern: '{quant.sf,cmd_info.json,lib_format_counts.json,aux_info,logs}'

    input:
    tuple val(meta), path(reads), path(transcriptome), path(transcriptome_index), val(quantification_params)

    output:
    tuple val(meta), path('salmon_quant'), emit: artifacts
    tuple val(meta), path('quant.sf'), path('cmd_info.json'),
        path('lib_format_counts.json'), path('aux_info'), path('logs'), emit: compatibility_files
    tuple val(meta), path("${meta.id}.quantification_logs"), path("${meta.id}.quantification_statistics"), emit: reports
    tuple val(meta), path("${meta.id}.versions.yml"), emit: versions
    tuple val(meta), path("${meta.id}.execution.json"), emit: execution_metadata
    tuple val(meta), path("${meta.id}.manifest.json"), emit: manifest
    tuple val(meta), path("${meta.id}.salmon_quant.done"), emit: status

    script:
    def read_list = reads instanceof List ? reads : [reads]
    def read_r1 = read_list[0]
    def read_r2 = meta.single_end ? null : read_list[1]
    def read_args = meta.single_end ? "-r '${read_r1}'" : "-1 '${read_r1}' -2 '${read_r2}'"
    def checksum_args = meta.single_end ? "'${read_r1}'" : "'${read_r1}' '${read_r2}'"
    def lib_type = quantification_params.lib_type
    def validate_value = quantification_params.validate_mappings
    def validate_mappings = validate_value instanceof Boolean ? validate_value : validate_value.toString().toBoolean()
    def validate_arg = validate_mappings ? '--validateMappings' : ''
    def target_dir = meta.target_dir ?: ''
    """
    start_epoch=\$(date +%s)
    logs_dir='${meta.id}.quantification_logs'
    stats_dir='${meta.id}.quantification_statistics'
    mkdir -p "\$logs_dir" "\$stats_dir"

    CMD=(
        salmon quant
        -i '${transcriptome_index}'
        -l '${lib_type}'
        ${read_args}
        -p ${task.cpus}
    )
    if [[ -n '${validate_arg}' ]]; then
        CMD+=('${validate_arg}')
    fi
    CMD+=(-o salmon_quant)
    printf '%q ' "\${CMD[@]}" > "\$logs_dir/command.txt"
    printf '\n' >> "\$logs_dir/command.txt"

    echo '[INFO] Salmon quant: ${meta.id}' | tee "\$logs_dir/salmon_quant.process.log"
    printf '+ %q ' "\${CMD[@]}" | tee -a "\$logs_dir/salmon_quant.process.log"
    printf '\n' | tee -a "\$logs_dir/salmon_quant.process.log"
    "\${CMD[@]}" 2>&1 | tee -a "\$logs_dir/salmon_quant.process.log"

    [[ -s salmon_quant/quant.sf ]]
    [[ -s salmon_quant/cmd_info.json ]]
    [[ -s salmon_quant/lib_format_counts.json ]]
    [[ -s salmon_quant/aux_info/meta_info.json ]]
    [[ -s salmon_quant/logs/salmon_quant.log ]]
    ln -s salmon_quant/quant.sf quant.sf
    ln -s salmon_quant/cmd_info.json cmd_info.json
    ln -s salmon_quant/lib_format_counts.json lib_format_counts.json
    ln -s salmon_quant/aux_info aux_info
    ln -s salmon_quant/logs logs
    cp salmon_quant/logs/salmon_quant.log "\$logs_dir/"

    transcriptome_sha=\$(sha256sum '${transcriptome}' | awk '{ print \$1 }')
    index_sha=\$(find '${transcriptome_index}' -type f -print0 \
        | sort -z | xargs -0 sha256sum | sha256sum | awk '{ print \$1 }')
    reads_sha=\$(sha256sum ${checksum_args} | awk '{ print \$1 }' | paste -sd, -)
    quant_sha=\$(sha256sum salmon_quant/quant.sf | awk '{ print \$1 }')
    cmd_sha=\$(sha256sum salmon_quant/cmd_info.json | awk '{ print \$1 }')
    library_sha=\$(sha256sum salmon_quant/lib_format_counts.json | awk '{ print \$1 }')
    auxiliary_sha=\$(find salmon_quant/aux_info -type f -print0 \
        | sort -z | xargs -0 sha256sum | sha256sum | awk '{ print \$1 }')

    awk -F '\t' '
        BEGIN { OFS="\t" }
        NR == 1 {
            for (i=1; i<=NF; i++) column[\$i]=i
            next
        }
        { transcripts++; sum_tpm += \$column["TPM"]; sum_reads += \$column["NumReads"] }
        END {
            print "metric", "value"
            print "transcripts", transcripts + 0
            printf "sum_tpm\t%.6f\\n", sum_tpm + 0
            printf "sum_num_reads\t%.6f\\n", sum_reads + 0
        }
    ' salmon_quant/quant.sf > "\$stats_dir/quantification.tsv"

    for metric in num_processed num_mapped percent_mapped; do
        value=\$(sed -n "/\\\"\${metric}\\\"/ { s/^[^:]*:[[:space:]]*//; s/[,\\\"]//g; p; q; }" \
            salmon_quant/aux_info/meta_info.json | tr -d ' ')
        [[ -z "\$value" ]] || printf '%s\t%s\n' "\$metric" "\$value" >> "\$stats_dir/quantification.tsv"
    done
    cp salmon_quant/lib_format_counts.json "\$stats_dir/"
    cp salmon_quant/aux_info/meta_info.json "\$stats_dir/"

    end_epoch=\$(date +%s)
    command_base64=\$(base64 -w0 "\$logs_dir/command.txt")

    printf '"%s":\n    salmon: "%s"\n' \
        '${task.process}' \
        "\$(salmon --version | awk '{ print \$NF }')" \
        > '${meta.id}.versions.yml'

    printf '{"id":"%s","process":"%s","command_base64":"%s","parameters":{"lib_type":"%s","validate_mappings":%s},"cpus":%s,"memory_bytes":%s,"time":"%s","container":"%s","transcriptome":"%s","transcriptome_sha256":"%s","index":"%s","index_sha256":"%s","reads_sha256":"%s","started_epoch":%s,"ended_epoch":%s,"elapsed_seconds":%s}\n' \
        '${meta.id}' '${task.process}' "\$command_base64" '${lib_type}' '${validate_mappings}' \
        '${task.cpus}' '${task.memory.toBytes()}' '${task.time}' '${params.salmon_container}' \
        '${transcriptome}' "\$transcriptome_sha" '${transcriptome_index}' "\$index_sha" "\$reads_sha" \
        "\$start_epoch" "\$end_epoch" "\$((end_epoch-start_epoch))" \
        > '${meta.id}.execution.json'

    printf '{"schema_version":"1.0","type":"quantification","id":"%s","status":"complete","quantifier":"salmon","dataset":"%s","sample_id":"%s","artifacts":{"quantification":{"path":"quant.sf","compatibility_path":"%s/quant.sf","sha256":"%s"},"command_info":{"path":"cmd_info.json","sha256":"%s"},"library_format":{"path":"lib_format_counts.json","sha256":"%s"},"auxiliary":{"path":"aux_info","sha256":"%s"}},"transcriptome_sha256":"%s","index_sha256":"%s"}\n' \
        '${meta.id}' '${meta.dataset}' '${meta.sample_id}' '${target_dir}' "\$quant_sha" "\$cmd_sha" \
        "\$library_sha" "\$auxiliary_sha" "\$transcriptome_sha" "\$index_sha" \
        > '${meta.id}.manifest.json'
    printf '{"id":"%s","process":"%s","status":"complete"}\n' \
        '${meta.id}' '${task.process}' > '${meta.id}.salmon_quant.done'
    """

    stub:
    """
    mkdir -p salmon_quant/aux_info salmon_quant/logs \
        '${meta.id}.quantification_logs' '${meta.id}.quantification_statistics'
    printf 'Name\tLength\tEffectiveLength\tTPM\tNumReads\ntx_stub\t100\t80.0\t1000000.0\t1.0\n' \
        > salmon_quant/quant.sf
    printf '{"salmon_version":"stub","index":"salmon_index","output":"salmon_quant"}\n' \
        > salmon_quant/cmd_info.json
    printf '{"expected_format":"A","compatible_fragment_ratio":1.0}\n' \
        > salmon_quant/lib_format_counts.json
    printf '{"num_processed":1,"num_mapped":1,"percent_mapped":100.0,"library_types":["IU"]}\n' \
        > salmon_quant/aux_info/meta_info.json
    printf 'tx_stub\t1\t0\n' > salmon_quant/aux_info/ambig_info.tsv
    printf 'stub\n' > salmon_quant/aux_info/fld.gz
    printf '[STUB] Salmon quant %s\n' '${meta.id}' > salmon_quant/logs/salmon_quant.log
    ln -s salmon_quant/quant.sf quant.sf
    ln -s salmon_quant/cmd_info.json cmd_info.json
    ln -s salmon_quant/lib_format_counts.json lib_format_counts.json
    ln -s salmon_quant/aux_info aux_info
    ln -s salmon_quant/logs logs
    printf 'salmon quant [stub]\n' > '${meta.id}.quantification_logs/command.txt'
    cp salmon_quant/logs/salmon_quant.log '${meta.id}.quantification_logs/'
    printf 'metric\tvalue\ntranscripts\t1\nsum_tpm\t1000000.000000\nsum_num_reads\t1.000000\nnum_processed\t1\nnum_mapped\t1\npercent_mapped\t100.0\n' \
        > '${meta.id}.quantification_statistics/quantification.tsv'
    cp salmon_quant/lib_format_counts.json salmon_quant/aux_info/meta_info.json \
        '${meta.id}.quantification_statistics/'
    printf '"SALMON_QUANT":\n    salmon: "stub"\n' > '${meta.id}.versions.yml'
    printf '{"id":"%s","process":"SALMON_QUANT","status":"stub"}\n' '${meta.id}' > '${meta.id}.execution.json'
    printf '{"schema_version":"1.0","type":"quantification","id":"%s","status":"stub","quantifier":"salmon"}\n' '${meta.id}' > '${meta.id}.manifest.json'
    printf '{"id":"%s","process":"SALMON_QUANT","status":"stub"}\n' '${meta.id}' > '${meta.id}.salmon_quant.done'
    """
}
