process PEAK_ANNOTATOR {
    tag "${meta.id}"
    label 'native_module'
    label 'peak_annotation_low'

    cpus 1
    memory 4.GB
    time 1.h
    cache 'deep'
    errorStrategy { task.exitStatus in [137, 143] ? 'retry' : 'terminate' }
    maxRetries 2

    container params.chipseq_peak_annotation_container
    conda "${moduleDir}/environment.yml"

    publishDir "${params.outdir}/pipeline_info/native_chipseq/peak_annotation/provider",
        mode: 'copy', overwrite: true, pattern: '*.{json,yml,done}'
    publishDir "${params.outdir}/chipseq/peak_annotation",
        mode: 'copy', overwrite: true, pattern: '*.peak_annotation'

    input:
    tuple val(meta), path(peaks), path(annotation), path(request)

    output:
    tuple val(meta), path("${meta.id}.peak_annotation"), emit: artifacts
    tuple val(meta), path("${meta.id}.peak_annotation/provider_reports"), emit: reports
    tuple val(meta), path("${meta.id}.peak_annotator.versions.yml"), emit: versions
    tuple val(meta), path("${meta.id}.peak_annotator.execution.json"), emit: execution_metadata
    tuple val(meta), path("${meta.id}.peak_annotator.manifest.json"), emit: manifest
    tuple val(meta), path("${meta.id}.peak_annotator.done"), emit: status

    script:
    """
    run_peak_annotator.py \
        --request '${request}' \
        --peaks '${peaks}' \
        --annotation '${annotation}' \
        --output-dir '${meta.id}.peak_annotation' \
        --manifest '${meta.id}.peak_annotator.manifest.json' \
        --execution '${meta.id}.peak_annotator.execution.json' \
        --versions '${meta.id}.peak_annotator.versions.yml' \
        --cpus '${task.cpus}' \
        --memory-bytes '${task.memory.toBytes()}' \
        --task-time '${task.time}' \
        --nextflow-version '${workflow.nextflow.version}'
    printf '{"id":"%s","process":"PEAK_ANNOTATOR","status":"complete"}\n' '${meta.id}' > '${meta.id}.peak_annotator.done'
    """

    stub:
    """
    mkdir -p '${meta.id}.peak_annotation/provider_reports'
    printf 'peak_id\tchrom\tstart\tend\tcategory\tgene_ids\tgene_count\tdistance_to_tss\trecord_id\tsource_id\tincluded\npeak_stub\tchrStub\t1\t9\tpromoter\tgene_stub\t1\t\tstub_record\tstub.peaks\ttrue\n' > '${meta.id}.peak_annotation/annotated_peaks.tsv'
    printf 'peak_id\tgene_id\tcategory\tdistance_to_tss\trecord_id\tsource_id\npeak_stub\tgene_stub\tpromoter\t\tstub_record\tstub.peaks\n' > '${meta.id}.peak_annotation/peak_gene_associations.tsv'
    printf 'feature\tcount\ngene\t1\npromoter\t1\n' > '${meta.id}.peak_annotation/provider_reports/annotation_features.tsv'
    printf '{"schema_version":"1.0","type":"peak_annotation","id":"%s","source_type":"peak_calling","source_id":"stub.peaks","record_id":"stub_record","record_ids":["stub_record"],"sample_ids":["stub_sample"],"genome_id":"stub_v1","build":"stub_v1","provider":"python_interval_v1","provider_version":"1.0.0","artifacts":{"annotated_peaks":{"path":"annotated_peaks.tsv","available":true},"peak_gene_associations":{"path":"peak_gene_associations.tsv","available":true}},"status":"stub"}\n' '${meta.id}' > '${meta.id}.peak_annotator.manifest.json'
    cp '${meta.id}.peak_annotator.manifest.json' '${meta.id}.peak_annotation/manifest.json'
    printf '{"schema_version":"1.0","id":"%s","process":"PEAK_ANNOTATOR","status":"stub"}\n' '${meta.id}' > '${meta.id}.peak_annotator.execution.json'
    printf '"PEAK_ANNOTATOR":\n    python: stub\n    provider: "python_interval_v1"\n' > '${meta.id}.peak_annotator.versions.yml'
    printf '{"id":"%s","process":"PEAK_ANNOTATOR","status":"stub"}\n' '${meta.id}' > '${meta.id}.peak_annotator.done'
    """
}
