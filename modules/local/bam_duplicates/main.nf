process BAM_DUPLICATES {
    tag "${meta.id}"
    label 'native_module'
    label 'bam_processing'

    cpus 8
    memory 32.GB
    time 12.h
    queue { params.bam_duplicates_queue ?: null }
    cache 'deep'
    errorStrategy { task.exitStatus in 130..145 ? 'retry' : 'terminate' }
    maxRetries 2

    container "${workflow.containerEngine in ['singularity', 'apptainer'] ? params.bam_samtools_apptainer_container : params.bam_samtools_container}"
    conda "${moduleDir}/environment.yml"

    publishDir "${params.outdir}/pipeline_info/native_chipseq/bam_duplicates",
        mode: 'copy', overwrite: true,
        pattern: '*.{json,yml,done,bam_duplicates_reports}'

    input:
    tuple val(meta), path(bam), val(duplicate_params), path(upstream_manifest)

    output:
    tuple val(meta), path("${meta.id}.duplicates.bam"), emit: artifacts
    tuple val(meta), path("${meta.id}.bam_duplicates_reports"), emit: reports
    tuple val(meta), path("${meta.id}.versions.yml"), emit: versions
    tuple val(meta), path("${meta.id}.execution.json"), emit: execution_metadata
    tuple val(meta), path("${meta.id}.bam_duplicates.manifest.json"), emit: manifest
    tuple val(meta), path("${meta.id}.bam_duplicates.done"), emit: status

    script:
    def mode = duplicate_params.mode
    """
    set -o pipefail
    start_epoch=\$(date +%s)
    output='${meta.id}.duplicates.bam'
    reports='${meta.id}.bam_duplicates_reports'
    mkdir -p "\$reports"
    [[ '${mode}' =~ ^(none|mark|remove)\$ ]] || { echo '[ERROR] duplicate mode must be none, mark, or remove' >&2; exit 2; }
    [[ -s '${bam}' ]] || { echo '[ERROR] input BAM is empty' >&2; exit 3; }
    samtools quickcheck -v '${bam}'
    sort_order=\$(samtools view -H '${bam}' | awk -F '\t' '\$1=="@HD" {for(i=2;i<=NF;i++) if(\$i ~ /^SO:/) {print substr(\$i,4); exit}}')
    [[ "\$sort_order" == 'coordinate' ]] || { echo "[ERROR] BAM_DUPLICATES requires coordinate-sorted input, got '\${sort_order:-missing}'" >&2; exit 3; }

    before=\$(samtools view -c '${bam}')
    duplicate_flags_before=\$(samtools view -c -f 1024 '${bam}')
    : > "\$reports/command.txt"

    if [[ '${mode}' == 'none' ]]; then
        printf 'cp %q %q\n' '${bam}' "\$output" > "\$reports/command.txt"
        cp '${bam}' "\$output"
        duplicates_detected="\$duplicate_flags_before"
        detection='preexisting_flags_only'
    else
        if [[ '${meta.single_end}' == 'false' ]]; then
            printf '%s\n' \
                "samtools sort -@ ${task.cpus} -n -o namesort.bam ${bam}" \
                "samtools fixmate -@ ${task.cpus} -m namesort.bam fixmate.bam" \
                "samtools sort -@ ${task.cpus} -o positionsort.bam fixmate.bam" \
                "samtools markdup -@ ${task.cpus} -s positionsort.bam marked.bam" \
                > "\$reports/command.txt"
            samtools sort -@ ${task.cpus} -n -o namesort.bam '${bam}'
            samtools fixmate -@ ${task.cpus} -m namesort.bam fixmate.bam
            samtools sort -@ ${task.cpus} -o positionsort.bam fixmate.bam
            markdup_input=positionsort.bam
        else
            printf 'samtools markdup -@ %s -s %q marked.bam\n' '${task.cpus}' '${bam}' > "\$reports/command.txt"
            markdup_input='${bam}'
        fi
        samtools markdup -@ ${task.cpus} -s "\$markdup_input" marked.bam \
            2> "\$reports/markdup.log"
        duplicates_detected=\$(samtools view -c -f 1024 marked.bam)
        detection='samtools_markdup'
        if [[ '${mode}' == 'remove' ]]; then
            printf 'samtools view -@ %s -b -F 1024 -o %q marked.bam\n' '${task.cpus}' "\$output" >> "\$reports/command.txt"
            samtools view -@ ${task.cpus} -b -F 1024 -o "\$output" marked.bam
        else
            cp marked.bam "\$output"
        fi
    fi

    samtools quickcheck -v "\$output"
    after=\$(samtools view -c "\$output")
    duplicates_after=\$(samtools view -c -f 1024 "\$output")
    removed=\$((before-after))
    if (( before > 0 )); then
        duplicate_percent=\$(awk -v d="\$duplicates_detected" -v n="\$before" 'BEGIN {printf "%.6f", 100*d/n}')
    else
        duplicate_percent='0.000000'
    fi
    printf 'metric\tvalue\nmode\t%s\ndetection\t%s\nreads_before\t%s\nduplicates_flagged_before\t%s\nduplicates_detected\t%s\nduplicate_percent\t%s\nreads_after\t%s\nduplicates_flagged_after\t%s\nreads_removed\t%s\n' \
        '${mode}' "\$detection" "\$before" "\$duplicate_flags_before" "\$duplicates_detected" "\$duplicate_percent" \
        "\$after" "\$duplicates_after" "\$removed" > "\$reports/metrics.tsv"
    samtools flagstat --threads ${task.cpus} "\$output" > "\$reports/flagstat.txt"

    input_sha=\$(sha256sum '${bam}' | awk '{print \$1}')
    output_sha=\$(sha256sum "\$output" | awk '{print \$1}')
    upstream_sha=\$(sha256sum '${upstream_manifest}' | awk '{print \$1}')
    command_base64=\$(base64 -w0 "\$reports/command.txt")
    end_epoch=\$(date +%s)
    printf '"%s":\n    samtools: %s\n' '${task.process}' "\$(samtools --version | sed -n '1s/samtools //p')" > '${meta.id}.versions.yml'
    printf '{"id":"%s","process":"%s","command_base64":"%s","duplicate_mode":"%s","input_sha256":"%s","output_sha256":"%s","reads_before":%s,"duplicates_detected":%s,"reads_after":%s,"cpus":%s,"memory_bytes":%s,"time":"%s","started_epoch":%s,"ended_epoch":%s,"elapsed_seconds":%s}\n' \
        '${meta.id}' '${task.process}' "\$command_base64" '${mode}' "\$input_sha" "\$output_sha" "\$before" "\$duplicates_detected" "\$after" \
        '${task.cpus}' '${task.memory.toBytes()}' '${task.time}' "\$start_epoch" "\$end_epoch" "\$((end_epoch-start_epoch))" > '${meta.id}.execution.json'
    printf '{"schema_version":"1.0","type":"bam_duplicates","id":"%s","status":"complete","policy":"%s","artifact":"%s","sha256":"%s","reads_before":%s,"duplicates_detected":%s,"reads_after":%s,"upstream_manifests":[{"sha256":"%s"}]}\n' \
        '${meta.id}' '${mode}' "\$output" "\$output_sha" "\$before" "\$duplicates_detected" "\$after" "\$upstream_sha" > '${meta.id}.bam_duplicates.manifest.json'
    printf '{"id":"%s","process":"%s","status":"complete"}\n' '${meta.id}' '${task.process}' > '${meta.id}.bam_duplicates.done'
    """

    stub:
    def mode = duplicate_params.mode
    """
    touch '${meta.id}.duplicates.bam'
    mkdir -p '${meta.id}.bam_duplicates_reports'
    printf 'samtools markdup [stub]\n' > '${meta.id}.bam_duplicates_reports/command.txt'
    printf '[STUB] duplicate policy ${mode}\n' > '${meta.id}.bam_duplicates_reports/markdup.log'
    printf 'metric\tvalue\nmode\t${mode}\nreads_before\t2\nduplicates_detected\t1\nduplicate_percent\t50.000000\nreads_after\t2\nreads_removed\t0\n' > '${meta.id}.bam_duplicates_reports/metrics.tsv'
    printf 'stub\n' > '${meta.id}.bam_duplicates_reports/flagstat.txt'
    printf '"BAM_DUPLICATES":\n    samtools: stub\n' > '${meta.id}.versions.yml'
    printf '{"id":"%s","process":"BAM_DUPLICATES","status":"stub"}\n' '${meta.id}' > '${meta.id}.execution.json'
    upstream_sha=\$(sha256sum '${upstream_manifest}' | awk '{print \$1}')
    printf '{"schema_version":"1.0","type":"bam_duplicates","id":"%s","status":"stub","policy":"${mode}","upstream_manifests":[{"sha256":"%s"}]}\n' '${meta.id}' "\$upstream_sha" > '${meta.id}.bam_duplicates.manifest.json'
    printf '{"id":"%s","process":"BAM_DUPLICATES","status":"stub"}\n' '${meta.id}' > '${meta.id}.bam_duplicates.done'
    """
}
