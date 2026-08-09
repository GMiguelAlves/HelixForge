process FEATURECOUNTS_PEAK {
    tag "${meta.id}"
    label 'native_module'
    label 'db_count'

    cpus 4
    memory 16.GB
    time 8.h
    queue { params.db_count_queue ?: null }
    cache 'deep'
    errorStrategy { task.exitStatus in 130..145 ? 'retry' : 'terminate' }
    maxRetries 2

    container { workflow.containerEngine in ['singularity', 'apptainer'] ? params.featurecounts_apptainer_container : params.featurecounts_container }
    conda "${moduleDir}/environment.yml"

    publishDir "${params.outdir}/pipeline_info/native_chipseq/differential_binding/counting",
        mode: 'copy', overwrite: true, pattern: '*.{json,yml,done,peak_count_reports}'
    publishDir { "${params.outdir}/chipseq/differential_binding/${meta.id}/counts" },
        mode: 'copy', overwrite: true, pattern: '*.peak_counts'

    input:
    tuple val(meta), path(peak_bed), path(bams), path(bais), path(bam_manifests), path(count_spec)

    output:
    tuple val(meta), path("${meta.id}.peak_counts"), path(count_spec), emit: artifacts
    tuple val(meta), path("${meta.id}.peak_count_reports"), emit: reports
    tuple val(meta), path("${meta.id}.peak_count.versions.yml"), emit: versions
    tuple val(meta), path("${meta.id}.peak_count.execution.json"), emit: execution_metadata
    tuple val(meta), path("${meta.id}.peak_count.manifest.json"), emit: manifest
    tuple val(meta), path("${meta.id}.peak_count.done"), emit: status

    script:
    def bamArgs = bams.collect { bam -> "--bam '${bam}'" }.join(' ')
    def baiArgs = bais.collect { bai -> "--bai '${bai}'" }.join(' ')
    def manifestArgs = bam_manifests.collect { manifest -> "--bam-manifest '${manifest}'" }.join(' ')
    def profile = workflow.profile ?: ''
    def gitCommit = workflow.commitId ?: 'unknown'
    """
    peak_featurecounts.py \
        --peaks '${peak_bed}' \
        ${bamArgs} \
        ${baiArgs} \
        ${manifestArgs} \
        --spec '${count_spec}' \
        --output-dir '${meta.id}.peak_counts' \
        --reports '${meta.id}.peak_count_reports' \
        --manifest '${meta.id}.peak_count.manifest.json' \
        --execution '${meta.id}.peak_count.execution.json' \
        --versions '${meta.id}.peak_count.versions.yml' \
        --cpus '${task.cpus}' \
        --memory-bytes '${task.memory.toBytes()}' \
        --task-time '${task.time}' \
        --nextflow-version '${workflow.nextflow.version}' \
        --profile '${profile}' \
        --git-commit '${gitCommit}' \
        --environment '${workflow.containerEngine ?: 'host'}'
    printf '{"id":"%s","process":"%s","status":"complete"}\n' \
        '${meta.id}' '${task.process}' > '${meta.id}.peak_count.done'
    """

    stub:
    """
    mkdir -p '${meta.id}.peak_counts' '${meta.id}.peak_count_reports'
    printf 'peak_id\tchrom\tstart\tend\tS1\tS2\npeak_000001\tchrStub\t4\t12\t10\t20\n' > '${meta.id}.peak_counts/raw_peak_counts.tsv'
    printf 'Status\tS1\tS2\nAssigned\t10\t20\n' > '${meta.id}.peak_counts/featurecounts_summary.tsv'
    printf 'GeneID\tChr\tStart\tEnd\tStrand\npeak_000001\tchrStub\t5\t12\t.\n' > '${meta.id}.peak_count_reports/peaks.saf'
    printf '[STUB] featureCounts peak counting\n' > '${meta.id}.peak_count_reports/command.txt'
    printf '{"schema_version":"1.0","type":"peak_count_matrix","id":"%s","provider":"featurecounts","artifacts":{"raw_counts":{"path":"raw_peak_counts.tsv","available":true}},"status":"stub"}\n' '${meta.id}' > '${meta.id}.peak_count.manifest.json'
    cp '${meta.id}.peak_count.manifest.json' '${meta.id}.peak_counts/manifest.json'
    printf '{"id":"%s","process":"FEATURECOUNTS_PEAK","status":"stub"}\n' '${meta.id}' > '${meta.id}.peak_count.execution.json'
    printf '"FEATURECOUNTS_PEAK":\n    featurecounts: stub\n    python: stub\n' > '${meta.id}.peak_count.versions.yml'
    printf '{"id":"%s","process":"FEATURECOUNTS_PEAK","status":"stub"}\n' '${meta.id}' > '${meta.id}.peak_count.done'
    """
}
