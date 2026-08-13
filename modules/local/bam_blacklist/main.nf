process BAM_BLACKLIST {
    tag "${meta.id}"
    label 'native_module'
    label 'bam_processing'

    cpus 8
    memory 32.GB
    time 12.h
    queue { params.bam_blacklist_queue ?: null }
    cache 'deep'
    errorStrategy { task.exitStatus in 130..145 ? 'retry' : 'terminate' }
    maxRetries 2

    container "${workflow.containerEngine in ['singularity', 'apptainer'] ? params.bam_samtools_apptainer_container : params.bam_samtools_container}"
    conda "${moduleDir}/environment.yml"

    publishDir "${params.outdir}/pipeline_info/native_chipseq/bam_blacklist",
        mode: 'copy', overwrite: true,
        pattern: '*.{json,yml,done,bam_blacklist_reports}'

    input:
    tuple val(meta), path(bam), path(bam_contigs), path(blacklist), val(blacklist_params), path(upstream_manifest)

    output:
    tuple val(meta), path("${meta.id}.blacklist.bam"), emit: artifacts
    tuple val(meta), path("${meta.id}.bam_blacklist_reports"), emit: reports
    tuple val(meta), path("${meta.id}.versions.yml"), emit: versions
    tuple val(meta), path("${meta.id}.execution.json"), emit: execution_metadata
    tuple val(meta), path("${meta.id}.bam_blacklist.manifest.json"), emit: manifest
    tuple val(meta), path("${meta.id}.bam_blacklist.done"), emit: status

    script:
    def mode = blacklist_params.overlap_mode ?: 'fragment'
    def has_blacklist = blacklist && (!(blacklist instanceof List) || !blacklist.isEmpty())
    def blacklist_file = has_blacklist ? blacklist.toString() : ''
    """
    set -o pipefail
    start_epoch=\$(date +%s)
    output='${meta.id}.blacklist.bam'
    reports='${meta.id}.bam_blacklist_reports'
    mkdir -p "\$reports"
    [[ '${mode}' =~ ^(alignment|fragment)\$ ]] || { echo '[ERROR] blacklist overlap_mode must be alignment or fragment' >&2; exit 2; }
    [[ -s '${bam}' && -s '${bam_contigs}' ]] || { echo '[ERROR] BAM and contig manifest must be non-empty' >&2; exit 3; }
    samtools quickcheck -v '${bam}'
    before=\$(samtools view -c '${bam}')

    if [[ '${has_blacklist}' == 'true' ]]; then
        [[ -s '${blacklist_file}' ]] || { echo '[ERROR] supplied blacklist BED is empty or missing' >&2; exit 3; }
        awk 'BEGIN {valid=0} {sub(/\\r\$/, "", \$0)} /^#/ || NF==0 {next} {
            if (NF < 3 || \$2 !~ /^[0-9]+\$/ || \$3 !~ /^[0-9]+\$/ || \$2 < 0 || \$3 <= \$2) {
                printf "invalid BED line %d: %s\\n", NR, \$0 > "/dev/stderr"; exit 1
            }
            valid++
        } END {if (valid == 0) {print "blacklist contains no intervals" > "/dev/stderr"; exit 1}}' '${blacklist_file}' \
            > "\$reports/bed_validation.log" 2>&1 || { cat "\$reports/bed_validation.log" >&2; exit 4; }
        awk '{sub(/\\r\$/, "", \$0)} NR==FNR {bam[\$1]=1; next} /^#/ || NF==0 {next} ! (\$1 in bam) {if (!(\$1 in missing)) {missing[\$1]=1; missing_count++}}
            END {for (contig in missing) print contig; if (missing_count>0) exit 1}' \
            '${bam_contigs}' '${blacklist_file}' > "\$reports/incompatible_contigs.txt" || {
                echo '[ERROR] blacklist contains contigs absent from the BAM/reference; no automatic renaming is performed.' >&2
                cat "\$reports/incompatible_contigs.txt" >&2
                exit 4
            }

        samtools index -@ ${task.cpus} '${bam}' '${bam}.bai'
        if [[ '${mode}' == 'alignment' ]]; then
            printf 'samtools view -@ %s -b -L %q -U %q -o blacklist_hits.bam %q\n' \
                '${task.cpus}' '${blacklist_file}' "\$output" '${bam}' > "\$reports/command.txt"
            samtools view -@ ${task.cpus} -b -L '${blacklist_file}' \
                -U "\$output" -o blacklist_hits.bam '${bam}' \
                2> "\$reports/bam_blacklist.log"
            blacklisted_templates='not_applicable'
        else
            printf '%s\n' \
                "samtools view -L ${blacklist_file} ${bam} | cut -f1 | sort -u > blacklisted_qnames.txt" \
                "samtools view -h ${bam} | awk [remove listed QNAMEs] | samtools view -b -o ${meta.id}.blacklist.bam -" \
                > "\$reports/command.txt"
            samtools view -@ ${task.cpus} -L '${blacklist_file}' '${bam}' \
                | cut -f1 | LC_ALL=C sort -u > blacklisted_qnames.txt
            blacklisted_templates=\$(wc -l < blacklisted_qnames.txt)
            if [[ -s blacklisted_qnames.txt ]]; then
                samtools view -h '${bam}' \
                    | awk 'NR==FNR {remove[\$1]=1; next} /^@/ {print; next} !(\$1 in remove)' blacklisted_qnames.txt - \
                    | samtools view -@ ${task.cpus} -b -o "\$output" - \
                    2> "\$reports/bam_blacklist.log"
            else
                cp '${bam}' "\$output"
                printf '[INFO] no alignments overlap blacklist\n' > "\$reports/bam_blacklist.log"
            fi
        fi
        blacklist_sha=\$(sha256sum '${blacklist_file}' | awk '{print \$1}')
        blacklist_path='${blacklist_file}'
    else
        printf 'cp %q %q # no blacklist supplied\n' '${bam}' "\$output" > "\$reports/command.txt"
        cp '${bam}' "\$output"
        printf '[INFO] blacklist disabled\n' > "\$reports/bam_blacklist.log"
        : > "\$reports/incompatible_contigs.txt"
        blacklist_sha='none'
        blacklist_path=''
        blacklisted_templates='0'
    fi

    samtools quickcheck -v "\$output"
    after=\$(samtools view -c "\$output")
    removed=\$((before-after))
    printf 'metric\tvalue\nblacklist_enabled\t%s\noverlap_mode\t%s\nreads_before\t%s\nreads_after\t%s\nreads_removed\t%s\nblacklisted_templates\t%s\n' \
        '${has_blacklist}' '${mode}' "\$before" "\$after" "\$removed" "\$blacklisted_templates" > "\$reports/metrics.tsv"

    input_sha=\$(sha256sum '${bam}' | awk '{print \$1}')
    output_sha=\$(sha256sum "\$output" | awk '{print \$1}')
    upstream_sha=\$(sha256sum '${upstream_manifest}' | awk '{print \$1}')
    command_base64=\$(base64 -w0 "\$reports/command.txt")
    end_epoch=\$(date +%s)
    printf '"%s":\n    samtools: %s\n' '${task.process}' "\$(samtools --version | sed -n '1s/samtools //p')" > '${meta.id}.versions.yml'
    printf '{"id":"%s","process":"%s","command_base64":"%s","blacklist_enabled":%s,"overlap_mode":"%s","blacklist":"%s","blacklist_sha256":"%s","input_sha256":"%s","output_sha256":"%s","reads_before":%s,"reads_after":%s,"cpus":%s,"memory_bytes":%s,"time":"%s","started_epoch":%s,"ended_epoch":%s,"elapsed_seconds":%s}\n' \
        '${meta.id}' '${task.process}' "\$command_base64" '${has_blacklist}' '${mode}' "\$blacklist_path" "\$blacklist_sha" \
        "\$input_sha" "\$output_sha" "\$before" "\$after" '${task.cpus}' '${task.memory.toBytes()}' '${task.time}' \
        "\$start_epoch" "\$end_epoch" "\$((end_epoch-start_epoch))" > '${meta.id}.execution.json'
    printf '{"schema_version":"1.0","type":"bam_blacklist","id":"%s","status":"complete","enabled":%s,"overlap_mode":"%s","artifact":"%s","sha256":"%s","blacklist_sha256":"%s","reads_removed":%s,"upstream_manifests":[{"sha256":"%s"}]}\n' \
        '${meta.id}' '${has_blacklist}' '${mode}' "\$output" "\$output_sha" "\$blacklist_sha" "\$removed" "\$upstream_sha" > '${meta.id}.bam_blacklist.manifest.json'
    printf '{"id":"%s","process":"%s","status":"complete"}\n' '${meta.id}' '${task.process}' > '${meta.id}.bam_blacklist.done'
    """

    stub:
    def mode = blacklist_params.overlap_mode ?: 'fragment'
    def has_blacklist = blacklist && (!(blacklist instanceof List) || !blacklist.isEmpty())
    """
    touch '${meta.id}.blacklist.bam'
    mkdir -p '${meta.id}.bam_blacklist_reports'
    printf 'samtools view -L [stub]\n' > '${meta.id}.bam_blacklist_reports/command.txt'
    printf '[STUB] blacklist enabled=${has_blacklist}\n' > '${meta.id}.bam_blacklist_reports/bam_blacklist.log'
    : > '${meta.id}.bam_blacklist_reports/incompatible_contigs.txt'
    printf 'metric\tvalue\nblacklist_enabled\t${has_blacklist}\noverlap_mode\t${mode}\nreads_before\t2\nreads_after\t1\nreads_removed\t1\nblacklisted_templates\t1\n' > '${meta.id}.bam_blacklist_reports/metrics.tsv'
    printf '"BAM_BLACKLIST":\n    samtools: stub\n' > '${meta.id}.versions.yml'
    printf '{"id":"%s","process":"BAM_BLACKLIST","status":"stub"}\n' '${meta.id}' > '${meta.id}.execution.json'
    upstream_sha=\$(sha256sum '${upstream_manifest}' | awk '{print \$1}')
    printf '{"schema_version":"1.0","type":"bam_blacklist","id":"%s","status":"stub","enabled":${has_blacklist},"upstream_manifests":[{"sha256":"%s"}]}\n' '${meta.id}' "\$upstream_sha" > '${meta.id}.bam_blacklist.manifest.json'
    printf '{"id":"%s","process":"BAM_BLACKLIST","status":"stub"}\n' '${meta.id}' > '${meta.id}.bam_blacklist.done'
    """
}
