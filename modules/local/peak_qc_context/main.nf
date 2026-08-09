process PEAK_QC_CONTEXT {
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

    publishDir "${params.outdir}/pipeline_info/native_chipseq/peak_qc/context",
        mode: 'copy', overwrite: true, pattern: '*.{json,yml,done,log}'

    input:
    tuple val(meta), path(bam), path(bai), path(bam_manifest), path(peaks), path(peak_manifest), path(reference), path(blacklist), val(spec_base64)

    output:
    tuple val(meta), path("${meta.peak_id}.peak_qc_request.json"), emit: artifacts
    tuple val(meta), path("${meta.peak_id}.peak_qc_context.json"), path("${meta.peak_id}.peak_qc_context.log"), emit: reports
    tuple val(meta), path("${meta.peak_id}.peak_qc_context.versions.yml"), emit: versions
    tuple val(meta), path("${meta.peak_id}.peak_qc_context.done"), emit: status

    script:
    def blacklistArg = blacklist ? "--blacklist '${blacklist}'" : ''
    """
    validate_peak_qc_context.py \
        --meta-base64 '${groovy.json.JsonOutput.toJson(meta).getBytes('UTF-8').encodeBase64().toString()}' \
        --bam '${bam}' \
        --bai '${bai}' \
        --bam-manifest '${bam_manifest}' \
        --peaks '${peaks}' \
        --peak-manifest '${peak_manifest}' \
        --reference '${reference}' \
        ${blacklistArg} \
        --spec-base64 '${spec_base64}' \
        --request '${meta.peak_id}.peak_qc_request.json' \
        --report '${meta.peak_id}.peak_qc_context.json' \
        2>&1 | tee '${meta.peak_id}.peak_qc_context.log'
    printf '"%s":\n    python: %s\n' '${task.process}' "\$(python3 --version | awk '{print \$2}')" > '${meta.peak_id}.peak_qc_context.versions.yml'
    printf '{"id":"%s","process":"%s","status":"complete"}\n' '${meta.peak_id}' '${task.process}' > '${meta.peak_id}.peak_qc_context.done'
    """

    stub:
    """
    printf '{"schema_version":"1.0","type":"peak_qc_request","id":"%s","record_id":"%s","sample_id":"%s","target":"%s","peak_type":"%s","caller":"%s","caller_version":"%s","unit":"fragments","filters":{"min_mapq":0,"duplicate_handling":"include","exclude_flags":2820},"overlap_strategy":"any_base","blacklist_policy":"bam_preprocessed","status":"stub"}\n' \
        '${meta.peak_id}' '${meta.record_id}' '${meta.sample_id}' '${meta.target}' '${meta.peak_type}' '${meta.caller}' '${meta.caller_version}' > '${meta.peak_id}.peak_qc_request.json'
    cp '${meta.peak_id}.peak_qc_request.json' '${meta.peak_id}.peak_qc_context.json'
    printf '[STUB] Peak QC context\n' > '${meta.peak_id}.peak_qc_context.log'
    printf '"PEAK_QC_CONTEXT":\n    python: stub\n' > '${meta.peak_id}.peak_qc_context.versions.yml'
    printf '{"id":"%s","process":"PEAK_QC_CONTEXT","status":"stub"}\n' '${meta.peak_id}' > '${meta.peak_id}.peak_qc_context.done'
    """
}
