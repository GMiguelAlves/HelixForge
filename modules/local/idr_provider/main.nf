process IDR_PROVIDER {
    tag "${meta.id}:idr"
    label 'native_module'
    label 'consensus_low'

    cpus 1
    memory 2.GB
    time 30.m
    cache 'deep'
    errorStrategy 'terminate'
    maxRetries 0

    container params.chipseq_metadata_container
    conda "${moduleDir}/environment.yml"

    publishDir "${params.outdir}/pipeline_info/native_chipseq/consensus/idr",
        mode: 'copy', overwrite: true, pattern: '*.{json,yml,done,idr_reports}'
    publishDir "${params.outdir}/chipseq/consensus/${meta.id}",
        mode: 'copy', overwrite: true, pattern: '*.idr_result'

    input:
    tuple val(meta), path(peak_dirs), path(request)

    output:
    tuple val(meta), path("${meta.id}.idr_result"), emit: artifacts
    tuple val(meta), path("${meta.id}.idr_reports"), emit: reports
    tuple val(meta), path("${meta.id}.idr.versions.yml"), emit: versions
    tuple val(meta), path("${meta.id}.idr.execution.json"), emit: execution_metadata
    tuple val(meta), path("${meta.id}.idr.manifest.json"), emit: manifest
    tuple val(meta), path("${meta.id}.idr.done"), emit: status

    script:
    def peakDirArgs = peak_dirs.collect { directory -> "--peak-dir '${directory}'" }.join(' ')
    """
    prepare_idr_provider.py \
        --request '${request}' \
        ${peakDirArgs} \
        --output-dir '${meta.id}.idr_result' \
        --reports '${meta.id}.idr_reports' \
        --manifest '${meta.id}.idr.manifest.json' \
        --execution '${meta.id}.idr.execution.json' \
        --versions '${meta.id}.idr.versions.yml' \
        --nextflow-version '${workflow.nextflow.version}'
    printf '{"id":"%s","process":"%s","strategy":"idr","status":"not_implemented"}\n' \
        '${meta.id}' '${task.process}' > '${meta.id}.idr.done'
    """

    stub:
    """
    mkdir -p '${meta.id}.idr_result' '${meta.id}.idr_reports'
    printf '{"schema_version":"1.0","id":"%s","strategy":"idr","idr_threshold":0.05,"rank_metric":"signal_value","status":"not_implemented"}\n' '${meta.id}' > '${meta.id}.idr_result/provider_request.json'
    printf '{"schema_version":"1.0","type":"idr","id":"%s","strategy":"idr","artifacts":{"consolidated_peaks":{"available":false}},"status":"not_implemented"}\n' '${meta.id}' > '${meta.id}.idr.manifest.json'
    cp '${meta.id}.idr.manifest.json' '${meta.id}.idr_result/manifest.json'
    printf '{"schema_version":"1.0","id":"%s","process":"IDR_PROVIDER","status":"not_implemented"}\n' '${meta.id}' > '${meta.id}.idr.execution.json'
    printf '"IDR_PROVIDER":\n    provider_runtime: not_implemented\n    python: stub\n' > '${meta.id}.idr.versions.yml'
    printf '[STUB] IDR provider abstraction; no statistical result produced\n' > '${meta.id}.idr_reports/provider.log'
    printf '{"id":"%s","process":"IDR_PROVIDER","strategy":"idr","status":"not_implemented"}\n' '${meta.id}' > '${meta.id}.idr.done'
    """
}
