process PEAK_QC_AGGREGATE {
    tag "${meta.id}"
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

    publishDir "${params.outdir}/pipeline_info/native_chipseq/peak_qc/aggregate",
        mode: 'copy', overwrite: true, pattern: '*.{json,yml,tsv,done}'
    publishDir "${params.outdir}/chipseq/peak_qc",
        mode: 'copy', overwrite: true, pattern: 'peak_qc_summary.{json,tsv}'

    input:
    tuple val(meta), path(frip_manifests), path(statistics_manifests)

    output:
    tuple val(meta), path('peak_qc_summary.json'), path('peak_qc_summary.tsv'), emit: artifacts
    tuple val(meta), path('peak_qc_summary.tsv'), emit: reports
    tuple val(meta), path('peak_qc_aggregate.versions.yml'), emit: versions
    tuple val(meta), path('peak_qc_aggregate.execution.json'), emit: execution_metadata
    tuple val(meta), path('peak_qc_manifest.json'), emit: manifest
    tuple val(meta), path('peak_qc_aggregate.done'), emit: status

    script:
    def fripArgs = frip_manifests.collect { manifest -> "--frip-manifest '${manifest}'" }.join(' ')
    def statisticsArgs = statistics_manifests.collect { manifest -> "--statistics-manifest '${manifest}'" }.join(' ')
    """
    peak_qc_aggregate.py \
        ${fripArgs} \
        ${statisticsArgs} \
        --summary-json peak_qc_summary.json \
        --summary-tsv peak_qc_summary.tsv \
        --manifest peak_qc_manifest.json \
        --execution peak_qc_aggregate.execution.json \
        --versions peak_qc_aggregate.versions.yml \
        --cpus '${task.cpus}' \
        --memory-bytes '${task.memory.toBytes()}' \
        --task-time '${task.time}'
    printf '{"id":"%s","process":"%s","status":"complete"}\n' '${meta.id}' '${task.process}' > peak_qc_aggregate.done
    """

    stub:
    """
    printf 'sample_id\ttarget\tbiological_replicate\ttechnical_replicate\tpeak_type\tcaller\tcaller_version\tunit\tpeak_count\tfrip\ttotal_units\tunits_in_peaks\nchip_rep1\tH3K27ac\t1\t1\tnarrow\tmacs3\t3.0.4\tfragments\t1\t1.0\t1\t1\nchip_rep2\tH3K27ac\t2\t1\tnarrow\tmacs3\t3.0.4\tfragments\t1\t1.0\t1\t1\n' > peak_qc_summary.tsv
    printf '{"schema_version":"1.0","type":"peak_qc_summary","records":2,"status":"stub"}\n' > peak_qc_summary.json
    printf '{"schema_version":"1.0","type":"peak_qc","id":"chipseq.peak_qc.aggregate","records":2,"status":"stub"}\n' > peak_qc_manifest.json
    printf '{"schema_version":"1.0","id":"chipseq.peak_qc.aggregate","process":"PEAK_QC_AGGREGATE","status":"stub"}\n' > peak_qc_aggregate.execution.json
    printf '"PEAK_QC_AGGREGATE":\n    python: stub\n' > peak_qc_aggregate.versions.yml
    printf '{"id":"chipseq.peak_qc.aggregate","process":"PEAK_QC_AGGREGATE","status":"stub"}\n' > peak_qc_aggregate.done
    """
}
