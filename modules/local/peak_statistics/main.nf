process PEAK_STATISTICS {
    tag "${meta.peak_id}"
    label 'native_module'
    label 'peak_qc_low'

    cpus 1
    memory 2.GB
    time 30.m
    cache 'deep'
    errorStrategy 'terminate'
    maxRetries 0

    container params.chipseq_metadata_container
    conda "${moduleDir}/environment.yml"

    publishDir "${params.outdir}/pipeline_info/native_chipseq/peak_qc/peak_statistics",
        mode: 'copy', overwrite: true, pattern: '*.{json,yml,tsv,done,peak_statistics_reports}'

    input:
    tuple val(meta), path(peaks), path(request)

    output:
    tuple val(meta), path("${meta.peak_id}.peak_statistics.json"), emit: artifacts
    tuple val(meta), path("${meta.peak_id}.peak_statistics_reports"), emit: reports
    tuple val(meta), path("${meta.peak_id}.peak_statistics.versions.yml"), emit: versions
    tuple val(meta), path("${meta.peak_id}.peak_statistics.execution.json"), emit: execution_metadata
    tuple val(meta), path("${meta.peak_id}.peak_statistics.manifest.json"), emit: manifest
    tuple val(meta), path("${meta.peak_id}.peak_statistics.done"), emit: status

    script:
    """
    peak_statistics.py \
        --request '${request}' \
        --peaks '${peaks}' \
        --output-json '${meta.peak_id}.peak_statistics.json' \
        --reports '${meta.peak_id}.peak_statistics_reports' \
        --versions '${meta.peak_id}.peak_statistics.versions.yml' \
        --execution '${meta.peak_id}.peak_statistics.execution.json' \
        --manifest '${meta.peak_id}.peak_statistics.manifest.json' \
        --cpus '${task.cpus}' \
        --memory-bytes '${task.memory.toBytes()}' \
        --task-time '${task.time}'
    printf '{"id":"%s","process":"%s","status":"complete"}\n' '${meta.peak_id}' '${task.process}' > '${meta.peak_id}.peak_statistics.done'
    """

    stub:
    """
    mkdir -p '${meta.peak_id}.peak_statistics_reports'
    printf 'metric\tvalue\npeak_count\t1\nvalid_peak_count\t1\npeak_width_min\t8\npeak_width_max\t8\npeak_width_mean\t8.0\npeak_width_median\t8\n' > '${meta.peak_id}.peak_statistics_reports/summary.tsv'
    printf 'peak_index\tpeak_name\tchromosome\twidth\n1\tstub\tchrStub\t8\n' > '${meta.peak_id}.peak_statistics_reports/peak_width_distribution.tsv'
    printf 'chromosome\tpeak_count\nchrStub\t1\n' > '${meta.peak_id}.peak_statistics_reports/peaks_by_chromosome.tsv'
    printf '{"schema_version":"1.0","id":"%s","peak_count":1,"valid_peak_count":1,"peak_width":{"min":8,"max":8,"mean":8.0,"median":8},"status":"stub"}\n' '${meta.peak_id}' > '${meta.peak_id}.peak_statistics.json'
    printf '{"schema_version":"1.0","type":"peak_qc_peak_statistics","id":"%s","status":"stub"}\n' '${meta.peak_id}' > '${meta.peak_id}.peak_statistics.manifest.json'
    printf '{"schema_version":"1.0","id":"%s","process":"PEAK_STATISTICS","status":"stub"}\n' '${meta.peak_id}' > '${meta.peak_id}.peak_statistics.execution.json'
    printf '"PEAK_STATISTICS":\n    python: stub\n' > '${meta.peak_id}.peak_statistics.versions.yml'
    printf '{"id":"%s","process":"PEAK_STATISTICS","status":"stub"}\n' '${meta.peak_id}' > '${meta.peak_id}.peak_statistics.done'
    """
}
