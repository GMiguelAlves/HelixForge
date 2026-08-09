process FRIP {
    tag "${meta.peak_id}"
    label 'native_module'
    label 'peak_qc'

    cpus 4
    memory 8.GB
    time 4.h
    queue { params.peak_qc_queue ?: null }
    cache 'deep'
    errorStrategy { task.exitStatus in 130..145 ? 'retry' : 'terminate' }
    maxRetries 2

    container "${workflow.containerEngine in ['singularity', 'apptainer'] ? params.peak_qc_apptainer_container : params.peak_qc_container}"
    conda "${moduleDir}/environment.yml"

    publishDir "${params.outdir}/pipeline_info/native_chipseq/peak_qc/frip",
        mode: 'copy', overwrite: true, pattern: '*.{json,yml,tsv,done,frip_reports}'

    input:
    tuple val(meta), path(bam), path(bai), path(peaks), path(request)

    output:
    tuple val(meta), path("${meta.peak_id}.frip.json"), path("${meta.peak_id}.frip.tsv"), emit: artifacts
    tuple val(meta), path("${meta.peak_id}.frip_reports"), emit: reports
    tuple val(meta), path("${meta.peak_id}.frip.versions.yml"), emit: versions
    tuple val(meta), path("${meta.peak_id}.frip.execution.json"), emit: execution_metadata
    tuple val(meta), path("${meta.peak_id}.frip.manifest.json"), emit: manifest
    tuple val(meta), path("${meta.peak_id}.frip.done"), emit: status

    script:
    """
    run_frip.py \
        --request '${request}' \
        --bam '${bam}' \
        --bai '${bai}' \
        --peaks '${peaks}' \
        --output-json '${meta.peak_id}.frip.json' \
        --output-tsv '${meta.peak_id}.frip.tsv' \
        --reports '${meta.peak_id}.frip_reports' \
        --versions '${meta.peak_id}.frip.versions.yml' \
        --execution '${meta.peak_id}.frip.execution.json' \
        --manifest '${meta.peak_id}.frip.manifest.json' \
        --cpus '${task.cpus}' \
        --memory-bytes '${task.memory.toBytes()}' \
        --task-time '${task.time}' \
        --environment '${workflow.containerEngine ?: 'host'}'
    printf '{"id":"%s","process":"%s","status":"complete"}\n' '${meta.peak_id}' '${task.process}' > '${meta.peak_id}.frip.done'
    """

    stub:
    """
    mkdir -p '${meta.peak_id}.frip_reports'
    printf 'chrStub\t0\t8\n' > '${meta.peak_id}.frip_reports/merged_peaks.bed'
    printf 'chrStub\t0\t8\tstub\n' > '${meta.peak_id}.frip_reports/units_in_peaks.bed'
    printf 'metric\tvalue\nfrip\t1.0\ntotal_fragments\t1\nfragments_in_peaks\t1\n' > '${meta.peak_id}.frip.tsv'
    printf '{"schema_version":"1.0","id":"%s","unit":"fragments","frip":1.0,"total_units":1,"units_in_peaks":1,"status":"stub"}\n' '${meta.peak_id}' > '${meta.peak_id}.frip.json'
    printf '{"schema_version":"1.0","type":"peak_qc_frip","id":"%s","metrics":{"frip":1.0,"total_units":1,"units_in_peaks":1},"status":"stub"}\n' '${meta.peak_id}' > '${meta.peak_id}.frip.manifest.json'
    printf '{"schema_version":"1.0","id":"%s","process":"FRIP","status":"stub"}\n' '${meta.peak_id}' > '${meta.peak_id}.frip.execution.json'
    printf '"FRIP":\n    samtools: stub\n    bedtools: stub\n    python: stub\n' > '${meta.peak_id}.frip.versions.yml'
    printf '{"id":"%s","process":"FRIP","status":"stub"}\n' '${meta.peak_id}' > '${meta.peak_id}.frip.done'
    """
}
