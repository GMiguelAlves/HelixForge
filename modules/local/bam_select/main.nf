process BAM_SELECT {
    tag "${meta.id}"
    label 'native_module'
    label 'bam_processing'

    cpus 8
    memory 32.GB
    time 12.h
    queue { params.bam_select_queue ?: null }
    cache 'deep'
    errorStrategy { task.exitStatus in 130..145 ? 'retry' : 'terminate' }
    maxRetries 2

    container "${workflow.containerEngine in ['singularity', 'apptainer'] ? params.bam_samtools_apptainer_container : params.bam_samtools_container}"
    conda "${moduleDir}/environment.yml"

    publishDir "${params.outdir}/pipeline_info/native_chipseq/bam_select",
        mode: 'copy', overwrite: true,
        pattern: '*.{json,yml,done,bam_select_reports}'

    input:
    tuple val(meta), path(bam), path(bai), path(reference), val(select_params)

    output:
    tuple val(meta), path("${meta.id}.selected.bam"), emit: artifacts
    tuple val(meta), path("${meta.id}.bam_select_reports"), emit: reports
    tuple val(meta), path("${meta.id}.versions.yml"), emit: versions
    tuple val(meta), path("${meta.id}.execution.json"), emit: execution_metadata
    tuple val(meta), path("${meta.id}.manifest.json"), emit: manifest
    tuple val(meta), path("${meta.id}.bam_select.done"), emit: status

    script:
    def min_mapq = select_params.min_mapq
    def include_flags = select_params.include_flags
    def exclude_flags = select_params.exclude_flags
    def region = select_params.region ?: ''
    def region_arg = region ? "'${region}'" : ''
    """
    set -o pipefail
    start_epoch=\$(date +%s)
    output='${meta.id}.selected.bam'
    reports='${meta.id}.bam_select_reports'
    mkdir -p "\$reports"

    [[ '${min_mapq}' =~ ^[0-9]+\$ ]] && (( ${min_mapq} <= 255 )) || { echo '[ERROR] min_mapq must be an integer from 0 to 255' >&2; exit 2; }
    [[ '${include_flags}' =~ ^[0-9]+\$ ]] && (( ${include_flags} <= 65535 )) || { echo '[ERROR] include_flags must be an integer from 0 to 65535' >&2; exit 2; }
    [[ '${exclude_flags}' =~ ^[0-9]+\$ ]] && (( ${exclude_flags} <= 65535 )) || { echo '[ERROR] exclude_flags must be an integer from 0 to 65535' >&2; exit 2; }
    [[ -s '${bam}' && -s '${bai}' && -s '${reference}' ]] || { echo '[ERROR] BAM, BAI, and reference must be non-empty' >&2; exit 3; }

    samtools quickcheck -v '${bam}' 2> "\$reports/quickcheck.log" || { cat "\$reports/quickcheck.log" >&2; exit 3; }
    if [[ '${bai}' != '${bam}.bai' ]]; then
        ln -sf "\$(realpath '${bai}')" '${bam}.bai'
    fi
    samtools idxstats '${bam}' > "\$reports/input.idxstats.tsv"

    samtools faidx '${reference}'
    samtools view -H '${bam}' | awk -F '\t' '
        \$1 == "@SQ" {
            sn=""; ln=""
            for (i=2; i<=NF; i++) {
                if (\$i ~ /^SN:/) sn=substr(\$i,4)
                if (\$i ~ /^LN:/) ln=substr(\$i,4)
            }
            if (sn != "" && ln != "") print sn "\t" ln
        }
    ' > "\$reports/bam_contigs.tsv"
    cut -f1,2 '${reference}.fai' > "\$reports/reference_contigs.tsv"
    if ! diff -u "\$reports/reference_contigs.tsv" "\$reports/bam_contigs.tsv" > "\$reports/reference_compatibility.diff"; then
        echo '[ERROR] BAM header and reference FASTA contigs/lengths are incompatible; no automatic renaming is performed.' >&2
        cat "\$reports/reference_compatibility.diff" >&2
        exit 4
    fi
    sort_order=\$(samtools view -H '${bam}' | awk -F '\t' '\$1=="@HD" {for(i=2;i<=NF;i++) if(\$i ~ /^SO:/) {print substr(\$i,4); exit}}')
    [[ "\$sort_order" == 'coordinate' ]] || { echo "[ERROR] BAM sort order is '\${sort_order:-missing}', expected coordinate" >&2; exit 4; }

    printf 'samtools view -@ %s -b -q %s -f %s -F %s -o %q %q %s\n' \
        '${task.cpus}' '${min_mapq}' '${include_flags}' '${exclude_flags}' "\$output" '${bam}' '${region}' \
        > "\$reports/command.txt"
    samtools view -@ ${task.cpus} -b \
        -q '${min_mapq}' -f '${include_flags}' -F '${exclude_flags}' \
        -o "\$output" '${bam}' ${region_arg} \
        2> "\$reports/bam_select.log"
    samtools quickcheck -v "\$output"

    before=\$(samtools view -c '${bam}')
    after=\$(samtools view -c "\$output")
    mapped=\$(samtools view -c -F 4 "\$output")
    proper=\$(samtools view -c -f 2 "\$output")
    printf 'metric\tvalue\ntotal_before\t%s\ntotal_after\t%s\nreads_removed\t%s\nmapped_after\t%s\nproperly_paired_after\t%s\n' \
        "\$before" "\$after" "\$((before-after))" "\$mapped" "\$proper" > "\$reports/metrics.tsv"
    {
        printf 'mapq\talignments\n'
        samtools view "\$output" | awk '{count[\$5]++} END {for (mapq in count) print mapq "\t" count[mapq]}' | sort -n
    } > "\$reports/mapq_distribution.tsv"
    printf 'parameter\tvalue\nmin_mapq\t%s\ninclude_flags\t%s\nexclude_flags\t%s\nregion\t%s\nlayout\t%s\n' \
        '${min_mapq}' '${include_flags}' '${exclude_flags}' '${region}' '${meta.single_end ? 'single' : 'paired'}' \
        > "\$reports/parameters.tsv"

    reference_sha=\$(sha256sum '${reference}' | awk '{print \$1}')
    input_sha=\$(sha256sum '${bam}' | awk '{print \$1}')
    output_sha=\$(sha256sum "\$output" | awk '{print \$1}')
    command_base64=\$(base64 -w0 "\$reports/command.txt")
    end_epoch=\$(date +%s)
    printf '"%s":\n    samtools: %s\n' '${task.process}' "\$(samtools --version | sed -n '1s/samtools //p')" > '${meta.id}.versions.yml'
    printf '{"id":"%s","process":"%s","command_base64":"%s","min_mapq":%s,"include_flags":%s,"exclude_flags":%s,"region":"%s","input_sha256":"%s","reference_sha256":"%s","output_sha256":"%s","cpus":%s,"memory_bytes":%s,"time":"%s","started_epoch":%s,"ended_epoch":%s,"elapsed_seconds":%s}\n' \
        '${meta.id}' '${task.process}' "\$command_base64" '${min_mapq}' '${include_flags}' '${exclude_flags}' '${region}' \
        "\$input_sha" "\$reference_sha" "\$output_sha" '${task.cpus}' '${task.memory.toBytes()}' '${task.time}' \
        "\$start_epoch" "\$end_epoch" "\$((end_epoch-start_epoch))" > '${meta.id}.execution.json'
    printf '{"schema_version":"0.1","type":"bam_selection","id":"%s","artifact":"%s","sha256":"%s","reference_sha256":"%s","parameters":{"min_mapq":%s,"include_flags":%s,"exclude_flags":%s,"region":"%s"}}\n' \
        '${meta.id}' "\$output" "\$output_sha" "\$reference_sha" '${min_mapq}' '${include_flags}' '${exclude_flags}' '${region}' \
        > '${meta.id}.manifest.json'
    printf '{"id":"%s","process":"%s","status":"complete"}\n' '${meta.id}' '${task.process}' > '${meta.id}.bam_select.done'
    """

    stub:
    def min_mapq = select_params.min_mapq
    def include_flags = select_params.include_flags
    def exclude_flags = select_params.exclude_flags
    def region = select_params.region ?: ''
    """
    touch '${meta.id}.selected.bam'
    mkdir -p '${meta.id}.bam_select_reports'
    printf 'chrStub\t16\n' > '${meta.id}.bam_select_reports/bam_contigs.tsv'
    cp '${meta.id}.bam_select_reports/bam_contigs.tsv' '${meta.id}.bam_select_reports/reference_contigs.tsv'
    : > '${meta.id}.bam_select_reports/reference_compatibility.diff'
    printf 'metric\tvalue\ntotal_before\t4\ntotal_after\t2\nreads_removed\t2\nmapped_after\t2\nproperly_paired_after\t2\n' > '${meta.id}.bam_select_reports/metrics.tsv'
    printf 'mapq\talignments\n42\t2\n' > '${meta.id}.bam_select_reports/mapq_distribution.tsv'
    printf 'parameter\tvalue\nmin_mapq\t${min_mapq}\ninclude_flags\t${include_flags}\nexclude_flags\t${exclude_flags}\nregion\t${region}\n' > '${meta.id}.bam_select_reports/parameters.tsv'
    printf 'samtools view [stub]\n' > '${meta.id}.bam_select_reports/command.txt'
    printf '[STUB] BAM selection\n' > '${meta.id}.bam_select_reports/bam_select.log'
    printf '"BAM_SELECT":\n    samtools: stub\n' > '${meta.id}.versions.yml'
    printf '{"id":"%s","process":"BAM_SELECT","status":"stub"}\n' '${meta.id}' > '${meta.id}.execution.json'
    printf '{"schema_version":"0.1","type":"bam_selection","id":"%s"}\n' '${meta.id}' > '${meta.id}.manifest.json'
    printf '{"id":"%s","process":"BAM_SELECT","status":"stub"}\n' '${meta.id}' > '${meta.id}.bam_select.done'
    """
}
