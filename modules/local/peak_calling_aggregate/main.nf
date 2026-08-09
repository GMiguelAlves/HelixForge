process PEAK_CALLING_AGGREGATE {
    tag "${meta.peak_id}"
    label 'native_module'
    label 'peak_calling_low'

    cpus 1
    memory 2.GB
    time 30.m
    cache 'deep'
    errorStrategy 'terminate'
    maxRetries 0

    container params.chipseq_metadata_container
    conda "${moduleDir}/environment.yml"

    publishDir "${params.outdir}/pipeline_info/native_chipseq/peak_calling/aggregate",
        mode: 'copy', overwrite: true, pattern: '*.{json,yml,tsv,done}'
    publishDir { meta.peak_target_dir }, mode: 'copy', overwrite: true, pattern: '*.peak_calling'

    input:
    tuple val(meta), path(provider_peaks), path(provider_dir), path(provider_manifest), val(request_base64)

    output:
    tuple val(meta), path("${meta.peak_id}.peak_calling"), emit: artifacts
    tuple val(meta), path("${meta.peak_id}.peak_metrics.json"), path("${meta.peak_id}.peak_metrics.tsv"), emit: reports
    tuple val(meta), path("${meta.peak_id}.aggregate.versions.yml"), emit: versions
    tuple val(meta), path("${meta.peak_id}.aggregate.execution.json"), emit: execution_metadata
    tuple val(meta), path("${meta.peak_id}.manifest.json"), emit: manifest
    tuple val(meta), path("${meta.peak_id}.peak_calling.done"), emit: status

    script:
    """
    start_epoch=\$(date +%s)
    aggregate_peaks.py \
        --request-base64 '${request_base64}' \
        --provider-peaks '${provider_peaks}' \
        --provider-dir '${provider_dir}' \
        --provider-manifest '${provider_manifest}' \
        --output-dir '${meta.peak_id}.peak_calling' \
        --manifest '${meta.peak_id}.manifest.json' \
        --metrics-json '${meta.peak_id}.peak_metrics.json' \
        --metrics-tsv '${meta.peak_id}.peak_metrics.tsv'
    end_epoch=\$(date +%s)
    printf '{"schema_version":"1.0","id":"%s","process":"%s","cpus":%s,"memory_bytes":%s,"started_epoch":%s,"ended_epoch":%s,"elapsed_seconds":%s}\n' \
        '${meta.peak_id}' '${task.process}' '${task.cpus}' '${task.memory.toBytes()}' "\$start_epoch" "\$end_epoch" "\$((end_epoch-start_epoch))" \
        > '${meta.peak_id}.aggregate.execution.json'
    printf '"%s":\n    python: %s\n' '${task.process}' "\$(python3 --version | awk '{print \$2}')" > '${meta.peak_id}.aggregate.versions.yml'
    printf '{"id":"%s","process":"%s","status":"complete"}\n' '${meta.peak_id}' '${task.process}' > '${meta.peak_id}.peak_calling.done'
    """

    stub:
    """
    mkdir -p '${meta.peak_id}.peak_calling/caller_outputs'
    cp '${provider_peaks}' '${meta.peak_id}.peak_calling/peaks.narrowPeak'
    printf '{"schema_version":"1.0","id":"%s","total_peaks":1,"status":"stub"}\n' '${meta.peak_id}' > '${meta.peak_id}.peak_metrics.json'
    printf 'metric\tvalue\ntotal_peaks\t1\n' > '${meta.peak_id}.peak_metrics.tsv'
    cp '${meta.peak_id}.peak_metrics.json' '${meta.peak_id}.peak_calling/peak_metrics.json'
    cp '${meta.peak_id}.peak_metrics.tsv' '${meta.peak_id}.peak_calling/peak_metrics.tsv'
    printf '{"schema_version":"1.0","type":"peak_calling","id":"%s","record_id":"%s","sample_id":"%s","experiment_id":"%s","target":"%s","biological_replicate":"%s","technical_replicate":"%s","control_id":"%s","control_record_id":"%s","caller":"%s","caller_version":"%s","peak_type":"%s","status":"stub"}\n' \
        '${meta.peak_id}' '${meta.record_id}' '${meta.sample_id}' '${meta.experiment_id}' '${meta.target}' \
        '${meta.biological_replicate}' '${meta.technical_replicate}' '${meta.control_id}' '${meta.control_record_id}' \
        '${meta.caller}' '${meta.caller_version}' '${meta.peak_type}' > '${meta.peak_id}.manifest.json'
    cp '${meta.peak_id}.manifest.json' '${meta.peak_id}.peak_calling/manifest.json'
    printf '{"schema_version":"1.0","id":"%s","process":"PEAK_CALLING_AGGREGATE","status":"stub"}\n' '${meta.peak_id}' > '${meta.peak_id}.aggregate.execution.json'
    printf '"PEAK_CALLING_AGGREGATE":\n    python: stub\n' > '${meta.peak_id}.aggregate.versions.yml'
    printf '{"id":"%s","process":"PEAK_CALLING_AGGREGATE","status":"stub"}\n' '${meta.peak_id}' > '${meta.peak_id}.peak_calling.done'
    """
}
