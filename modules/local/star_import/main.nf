process STAR_IMPORT {
    tag "${meta.id}"
    label 'native_module'
    label 'import_medium'

    cpus 2
    memory 32.GB
    time 6.h
    queue { params.star_import_queue ?: null }
    cache 'deep'
    errorStrategy { task.exitStatus in 130..145 ? 'retry' : 'terminate' }
    maxRetries 2

    container "${workflow.containerEngine in ['singularity', 'apptainer'] ? params.star_import_apptainer_container : params.star_import_container}"
    conda "${moduleDir}/environment.yml"

    publishDir { meta.target_dir }, mode: 'copy', overwrite: true,
        pattern: '{counts_matrix.tsv,star_cpm_matrix.tsv,quant_samples.tsv}'
    publishDir "${params.outdir}/pipeline_info/native_import/star_import",
        mode: 'copy', overwrite: true,
        pattern: '*.{json,yml,log,done}'

    input:
    tuple val(meta), path(sample_table), val(import_params)
    path sources

    output:
    tuple val(meta), path('counts_matrix.tsv'), emit: counts
    tuple val(meta), path('star_cpm_matrix.tsv'), emit: abundance
    tuple val(meta), path('quant_samples.tsv'), emit: metadata
    tuple val(meta), path('import.log'), path('import_statistics.json'), emit: reports
    tuple val(meta), path('versions.yml'), emit: versions
    tuple val(meta), path('execution.json'), emit: execution_metadata
    tuple val(meta), path('import_manifest.json'), emit: manifest
    tuple val(meta), path('star_import.done'), emit: status
    tuple val(meta), path('counts_matrix.tsv'), path('star_cpm_matrix.tsv'), path('quant_samples.tsv'), emit: artifacts

    script:
    def sourceArgs = sources.collect { "'${it}'" }.join(' ')
    """
    start_epoch=\$(date +%s)
    python '${moduleDir}/bin/star_import.py' \
        --sample-table '${sample_table}' \
        --count-column '${import_params.star_count_column}' \
        --counts-name counts_matrix.tsv \
        --abundance-name star_cpm_matrix.tsv \
        --metadata-name quant_samples.tsv \
        > import.log 2>&1

    counts_sha=\$(sha256sum counts_matrix.tsv | awk '{print \$1}')
    abundance_sha=\$(sha256sum star_cpm_matrix.tsv | awk '{print \$1}')
    metadata_sha=\$(sha256sum quant_samples.tsv | awk '{print \$1}')
    sources_sha=\$(find ${sourceArgs} -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum | awk '{print \$1}')
    sample_count=\$(awk 'END {print NR-1}' quant_samples.tsv)
    end_epoch=\$(date +%s)
    python_version=\$(python --version 2>&1 | awk '{print \$2}')

    printf '"%s":\n    python: "%s"\n' '${task.process}' "\$python_version" > versions.yml
    printf '{"id":"%s","process":"%s","parameters":{"star_count_column":"%s"},"cpus":%s,"memory_bytes":%s,"time":"%s","container":"%s","sources_sha256":"%s","started_epoch":%s,"ended_epoch":%s,"elapsed_seconds":%s}\n' \
        '${meta.id}' '${task.process}' '${import_params.star_count_column}' '${task.cpus}' \
        '${task.memory.toBytes()}' '${task.time}' '${params.star_import_container}' "\$sources_sha" \
        "\$start_epoch" "\$end_epoch" "\$((end_epoch-start_epoch))" > execution.json
    printf '{"schema_version":"1.0","type":"import","id":"%s","provider":"star","sample_count":%s,"parameters":{"star_count_column":"%s"},"artifacts":{"counts":{"path":"counts_matrix.tsv","sha256":"%s","available":true},"abundance":{"path":"star_cpm_matrix.tsv","sha256":"%s","available":true},"lengths":{"available":false,"reason":"STAR GeneCounts does not estimate transcript effective lengths"},"experiment":{"available":false,"reason":"not emitted by STAR provider in Import API v1.0"},"metadata":{"path":"quant_samples.tsv","sha256":"%s","available":true}}}\n' \
        '${meta.id}' "\$sample_count" '${import_params.star_count_column}' "\$counts_sha" \
        "\$abundance_sha" "\$metadata_sha" > import_manifest.json
    printf '{"id":"%s","process":"%s","status":"complete"}\n' \
        '${meta.id}' '${task.process}' > star_import.done
    """

    stub:
    """
    printf 'gene_id\tSTUB__stub_sample\ngene_stub\t1\n' > counts_matrix.tsv
    printf 'gene_id\tSTUB__stub_sample\ngene_stub\t1000000.0\n' > star_cpm_matrix.tsv
    awk -F '\t' 'BEGIN{OFS="\t"} NR==1{for(i=1;i<=NF;i++) if(\$i !~ /^__/) keep[i]=1} {out=""; for(i=1;i<=NF;i++) if(keep[i]) out=out (out?OFS:"") \$i; print out}' '${sample_table}' > quant_samples.tsv
    printf '[STUB] STAR import\n' > import.log
    printf '{"provider":"star","samples":1,"genes":1}\n' > import_statistics.json
    printf '"STAR_IMPORT":\n    python: "stub"\n' > versions.yml
    printf '{"id":"%s","process":"STAR_IMPORT","status":"stub"}\n' '${meta.id}' > execution.json
    printf '{"schema_version":"1.0","type":"import","id":"%s","provider":"star","artifacts":{"lengths":{"available":false},"experiment":{"available":false}}}\n' '${meta.id}' > import_manifest.json
    printf '{"id":"%s","process":"STAR_IMPORT","status":"stub"}\n' '${meta.id}' > star_import.done
    """
}
