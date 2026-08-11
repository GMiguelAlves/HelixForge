process CONSENSUS_CONTEXT {
    tag "${meta.id}"
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

    publishDir "${params.outdir}/pipeline_info/native_chipseq/consensus/context",
        mode: 'copy', overwrite: true, pattern: '*.{json,yml,done,log}'

    input:
    tuple val(meta), path(peak_dirs), path(peak_manifests, stageAs: 'peak_manifests??/*'), path(qc_manifests, stageAs: 'qc_manifests??/*'), val(records_base64), val(spec_base64)

    output:
    tuple val(meta), path("${meta.id}.consensus_request.json"), emit: artifacts
    tuple val(meta), path("${meta.id}.consensus_context.json"), path("${meta.id}.consensus_context.log"), emit: reports
    tuple val(meta), path("${meta.id}.consensus_context.versions.yml"), emit: versions
    tuple val(meta), path("${meta.id}.consensus_context.done"), emit: status

    script:
    def peakDirArgs = peak_dirs.collect { directory -> "--peak-dir '${directory}'" }.join(' ')
    def peakManifestArgs = peak_manifests.collect { manifest -> "--peak-manifest '${manifest}'" }.join(' ')
    def qcManifestArgs = qc_manifests.collect { manifest -> "--qc-manifest '${manifest}'" }.join(' ')
    """
    validate_consensus_context.py \
        ${peakDirArgs} \
        ${peakManifestArgs} \
        ${qcManifestArgs} \
        --records-base64 '${records_base64}' \
        --spec-base64 '${spec_base64}' \
        --request '${meta.id}.consensus_request.json' \
        --report '${meta.id}.consensus_context.json' \
        2>&1 | tee '${meta.id}.consensus_context.log'
    printf '"%s":\n    python: %s\n' '${task.process}' "\$(python3 --version | awk '{print \$2}')" > '${meta.id}.consensus_context.versions.yml'
    printf '{"id":"%s","process":"%s","status":"complete"}\n' '${meta.id}' '${task.process}' > '${meta.id}.consensus_context.done'
    """

    stub:
    """
    printf '{"schema_version":"1.0","type":"consensus_idr_request","id":"%s","strategy":"%s","replicate_mode":"biological","replicate_policy":"require_premerged","replicate_count":2,"support_threshold":1,"peak_type":"narrow","status":"stub"}\n' \
        '${meta.id}' '${meta.strategy}' > '${meta.id}.consensus_request.json'
    cp '${meta.id}.consensus_request.json' '${meta.id}.consensus_context.json'
    printf '[STUB] Consensus/IDR context\n' > '${meta.id}.consensus_context.log'
    printf '"CONSENSUS_CONTEXT":\n    python: stub\n' > '${meta.id}.consensus_context.versions.yml'
    printf '{"id":"%s","process":"CONSENSUS_CONTEXT","status":"stub"}\n' '${meta.id}' > '${meta.id}.consensus_context.done'
    """
}
