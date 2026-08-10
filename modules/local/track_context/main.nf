process TRACK_CONTEXT {
    tag "${meta.id}"
    label 'native_module'
    label 'track_low'

    cpus 1
    memory 2.GB
    time 30.m
    cache 'deep'
    errorStrategy 'terminate'
    maxRetries 0

    container params.chipseq_track_container
    conda "${moduleDir}/environment.yml"

    publishDir "${params.outdir}/pipeline_info/native_chipseq/tracks/context",
        mode: 'copy', overwrite: true, pattern: '*.{json,yml,done,log}'

    input:
    tuple val(meta), path(bams), path(bais), path(bam_manifests), path(reference), path(reference_manifest), val(spec_base64)

    output:
    tuple val(meta), path("${meta.id}.track_request.json"), emit: artifacts
    tuple val(meta), path("${meta.id}.track_context.json"), path("${meta.id}.track_context.log"), emit: reports
    tuple val(meta), path("${meta.id}.track_context.versions.yml"), emit: versions
    tuple val(meta), path("${meta.id}.track_context.done"), emit: status

    script:
    def bamArgs = bams.collect { value -> "--bam '${value}'" }.join(' ')
    def baiArgs = bais.collect { value -> "--bai '${value}'" }.join(' ')
    def manifestArgs = bam_manifests.collect { value -> "--bam-manifest '${value}'" }.join(' ')
    """
    validate_track_context.py \
        --meta-base64 '${groovy.json.JsonOutput.toJson(meta).getBytes('UTF-8').encodeBase64().toString()}' \
        ${bamArgs} \
        ${baiArgs} \
        ${manifestArgs} \
        --reference '${reference}' \
        --reference-manifest '${reference_manifest}' \
        --spec-base64 '${spec_base64}' \
        --request '${meta.id}.track_request.json' \
        --report '${meta.id}.track_context.json' \
        2>&1 | tee '${meta.id}.track_context.log'
    printf '"TRACK_CONTEXT":\n    python: "%s"\n    samtools: "%s"\n' \
        "\$(python3 --version | awk '{print \$2}')" "\$(samtools --version | sed -n '1s/samtools //p')" \
        > '${meta.id}.track_context.versions.yml'
    printf '{"id":"%s","process":"TRACK_CONTEXT","status":"complete"}\n' '${meta.id}' > '${meta.id}.track_context.done'
    """

    stub:
    """
    printf '{"schema_version":"1.0","type":"track_request","id":"%s","track_role":"%s","record_id":"%s","record_ids":["stub_record"],"sample_ids":["stub_sample"],"dataset":"stub","condition":"treated","target":"H3K27ac","genome_id":"stub_v1","build":"stub_v1","provider":"deeptools_bamcoverage_v1","provider_version":"1.0.0","parameters":{"track_format":"bigwig","bin_size":10,"normalization":"CPM","effective_genome_size":null,"scale_factor":1.0,"extend_reads":false,"fragment_mode":"reads","strand":"unstranded","additional_filters":"none"},"sources":[{"record_id":"stub_record","bam":"stub.filtered.bam","bai":"stub.filtered.bam.bai"}],"status":"stub"}\n' \
        '${meta.id}' '${meta.track_role}' '${meta.record_id ?: ''}' > '${meta.id}.track_request.json'
    cp '${meta.id}.track_request.json' '${meta.id}.track_context.json'
    printf '[STUB] Track context\n' > '${meta.id}.track_context.log'
    printf '"TRACK_CONTEXT":\n    python: stub\n    samtools: stub\n' > '${meta.id}.track_context.versions.yml'
    printf '{"id":"%s","process":"TRACK_CONTEXT","status":"stub"}\n' '${meta.id}' > '${meta.id}.track_context.done'
    """
}
