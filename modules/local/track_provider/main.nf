process TRACK_PROVIDER {
    tag "${meta.id}"
    label 'native_module'
    label 'track_medium'

    cpus 4
    memory 8.GB
    time 4.h
    cache 'deep'
    errorStrategy { task.exitStatus in [137, 143] ? 'retry' : 'terminate' }
    maxRetries 2

    container { workflow.containerEngine in ['singularity', 'apptainer'] ? params.chipseq_track_apptainer_container : params.chipseq_track_container }
    conda "${moduleDir}/environment.yml"

    publishDir "${params.outdir}/pipeline_info/native_chipseq/tracks/provider",
        mode: 'copy', overwrite: true, pattern: '*.{json,yml,done}'
    publishDir "${params.outdir}/chipseq/tracks",
        mode: 'copy', overwrite: true, pattern: '*.track_result'

    input:
    tuple val(meta), path(bams), path(bais), path(request)

    output:
    tuple val(meta), path("${meta.id}.track_result"), emit: artifacts
    tuple val(meta), path("${meta.id}.track_result/provider_reports"), emit: reports
    tuple val(meta), path("${meta.id}.track_provider.versions.yml"), emit: versions
    tuple val(meta), path("${meta.id}.track_provider.execution.json"), emit: execution_metadata
    tuple val(meta), path("${meta.id}.track_provider.manifest.json"), emit: manifest
    tuple val(meta), path("${meta.id}.track_provider.done"), emit: status

    script:
    def bamArgs = bams.collect { value -> "--bam '${value}'" }.join(' ')
    def baiArgs = bais.collect { value -> "--bai '${value}'" }.join(' ')
    """
    run_track_provider.py \
        --request '${request}' \
        ${bamArgs} \
        ${baiArgs} \
        --output-dir '${meta.id}.track_result' \
        --manifest '${meta.id}.track_provider.manifest.json' \
        --execution '${meta.id}.track_provider.execution.json' \
        --versions '${meta.id}.track_provider.versions.yml' \
        --cpus '${task.cpus}' \
        --memory-bytes '${task.memory.toBytes()}' \
        --task-time '${task.time}' \
        --nextflow-version '${workflow.nextflow.version}'
    printf '{"id":"%s","process":"TRACK_PROVIDER","status":"complete"}\n' '${meta.id}' > '${meta.id}.track_provider.done'
    """

    stub:
    """
    mkdir -p '${meta.id}.track_result/provider_reports'
    : > '${meta.id}.track_result/track.bw'
    printf 'bamCoverage --stub\n' > '${meta.id}.track_result/provider_reports/command.txt'
    printf '[STUB] Track provider\n' > '${meta.id}.track_result/provider_reports/provider.log'
    printf '{"schema_version":"1.0","id":"%s","source_reads":1,"mapped_reads":1,"track_bytes":0,"status":"stub"}\n' '${meta.id}' > '${meta.id}.track_result/provider_metrics.json'
    printf '{"schema_version":"1.0","type":"track_generation","id":"%s","track_role":"%s","record_id":"%s","record_ids":["stub_record"],"sample_ids":["stub_sample"],"genome_id":"stub_v1","build":"stub_v1","provider":"deeptools_bamcoverage_v1","provider_version":"1.0.0","parameters":{"track_format":"bigwig","bin_size":10,"normalization":"CPM","scale_factor":1.0,"fragment_mode":"reads"},"artifacts":{"primary_track":{"available":true,"path":"track.bw"},"provider_metrics":{"available":true,"path":"provider_metrics.json"}},"status":"stub"}\n' \
        '${meta.id}' '${meta.track_role}' '${meta.record_id ?: ''}' > '${meta.id}.track_provider.manifest.json'
    cp '${meta.id}.track_provider.manifest.json' '${meta.id}.track_result/manifest.json'
    printf '{"schema_version":"1.0","id":"%s","process":"TRACK_PROVIDER","status":"stub"}\n' '${meta.id}' > '${meta.id}.track_provider.execution.json'
    printf '"TRACK_PROVIDER":\n    deeptools: stub\n    samtools: stub\n    python: stub\n' > '${meta.id}.track_provider.versions.yml'
    printf '{"id":"%s","process":"TRACK_PROVIDER","status":"stub"}\n' '${meta.id}' > '${meta.id}.track_provider.done'
    """
}
