process PEAK_ANNOTATION_CONTEXT {
    tag "${meta.id}"
    label 'native_module'
    label 'peak_annotation_low'

    cpus 1
    memory 2.GB
    time 30.m
    cache 'deep'
    errorStrategy 'terminate'
    maxRetries 0

    container params.chipseq_peak_annotation_container
    conda "${moduleDir}/environment.yml"

    publishDir "${params.outdir}/pipeline_info/native_chipseq/peak_annotation/context",
        mode: 'copy', overwrite: true, pattern: '*.{json,yml,done,log}'

    input:
    tuple val(meta), path(peaks), path(peak_manifest), path(reference), path(reference_manifest), path(annotation), val(spec_base64)

    output:
    tuple val(meta), path("${meta.id}.peak_annotation_request.json"), emit: artifacts
    tuple val(meta), path("${meta.id}.peak_annotation_context.json"), path("${meta.id}.peak_annotation_context.log"), emit: reports
    tuple val(meta), path("${meta.id}.peak_annotation_context.versions.yml"), emit: versions
    tuple val(meta), path("${meta.id}.peak_annotation_context.done"), emit: status

    script:
    """
    set -o pipefail
    validate_peak_annotation_context.py \
        --meta-base64 '${groovy.json.JsonOutput.toJson(meta).getBytes('UTF-8').encodeBase64().toString()}' \
        --peaks '${peaks}' \
        --peak-manifest '${peak_manifest}' \
        --reference '${reference}' \
        --reference-manifest '${reference_manifest}' \
        --annotation '${annotation}' \
        --spec-base64 '${spec_base64}' \
        --request '${meta.id}.peak_annotation_request.json' \
        --report '${meta.id}.peak_annotation_context.json' \
        2>&1 | tee '${meta.id}.peak_annotation_context.log'
    printf '"PEAK_ANNOTATION_CONTEXT":\n    python: "%s"\n' "\$(python3 --version | awk '{print \$2}')" > '${meta.id}.peak_annotation_context.versions.yml'
    printf '{"id":"%s","process":"PEAK_ANNOTATION_CONTEXT","status":"complete"}\n' '${meta.id}' > '${meta.id}.peak_annotation_context.done'
    """

    stub:
    """
    printf '{"schema_version":"1.0","type":"peak_annotation_request","id":"%s","source_type":"peak_calling","source_id":"stub.peaks","record_id":"stub_record","sample_ids":["stub_sample"],"genome_id":"stub_v1","build":"stub_v1","provider":"python_interval_v1","parameters":{"mode":"overlap_priority","overlap_mode":"any","promoter_upstream":2000,"promoter_downstream":500,"max_tss_distance":null,"feature_priority":["promoter","exon","intron","downstream","gene"],"gene_assignment":"first","strand_aware":false,"intergenic_policy":"retain"},"status":"stub"}\n' '${meta.id}' > '${meta.id}.peak_annotation_request.json'
    cp '${meta.id}.peak_annotation_request.json' '${meta.id}.peak_annotation_context.json'
    printf '[STUB] Peak annotation context\n' > '${meta.id}.peak_annotation_context.log'
    printf '"PEAK_ANNOTATION_CONTEXT":\n    python: stub\n' > '${meta.id}.peak_annotation_context.versions.yml'
    printf '{"id":"%s","process":"PEAK_ANNOTATION_CONTEXT","status":"stub"}\n' '${meta.id}' > '${meta.id}.peak_annotation_context.done'
    """
}
