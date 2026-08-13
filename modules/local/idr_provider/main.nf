process IDR_PROVIDER {
    tag "${meta.id}:idr"
    label 'native_module'
    label 'consensus'

    cpus 2
    memory 4.GB
    time 2.h
    queue { params.idr_queue ?: params.consensus_queue ?: null }
    cache 'deep'
    errorStrategy 'terminate'
    maxRetries 0

    container { workflow.containerEngine in ['singularity', 'apptainer'] ? params.idr_apptainer_container : params.idr_container }
    conda "${moduleDir}/environment.yml"

    publishDir "${params.outdir}/pipeline_info/native_chipseq/consensus/idr",
        mode: 'copy', overwrite: true, pattern: '*.{json,yml,done,idr_reports}'
    publishDir { "${params.outdir}/chipseq/consensus/${meta.id}" },
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
    python '${moduleDir}/resources/usr/bin/run_idr.py' \
        --request '${request}' \
        ${peakDirArgs} \
        --output-dir '${meta.id}.idr_result' \
        --reports '${meta.id}.idr_reports' \
        --manifest '${meta.id}.idr.manifest.json' \
        --execution '${meta.id}.idr.execution.json' \
        --versions '${meta.id}.idr.versions.yml' \
        --nextflow-version '${workflow.nextflow.version}' \
        --cpus '${task.cpus}' \
        --memory-bytes '${task.memory.toBytes()}' \
        --task-time '${task.time}' \
        --environment '${workflow.containerEngine ?: 'host'}'
    printf '{"id":"%s","process":"%s","strategy":"idr","status":"complete"}\n' \
        '${meta.id}' '${task.process}' > '${meta.id}.idr.done'
    """

    stub:
    """
    mkdir -p '${meta.id}.idr_result' '${meta.id}.idr_reports'
    printf 'peak_id\tchrom\tstart\tend\tname\tscore\tstrand\tsignal_value\tp_value\tq_value\tsummit\tlocal_idr_score\tglobal_idr_score\tlocal_idr\tglobal_idr\n%s.idr.000001\tchrStub\t4\t12\tp1\t540\t.\t5\t10\t8\t4\t1.4\t1.30103\t0.0398\t0.05\n' '${meta.id}' > '${meta.id}.idr_result/consolidated_peaks.tsv'
    printf 'chrStub\t4\t12\t%s.idr.000001\n' '${meta.id}' > '${meta.id}.idr_result/consolidated_peaks.bed'
    printf 'chrStub\t4\t12\tp1\t540\t.\t5\t10\t8\t4\t1.4\t1.30103\n' > '${meta.id}.idr_result/idr_output.narrowPeak'
    printf 'replicate_id\tpeak_id\tpeak_file\tpeak_sha256\tinput_peaks\n1\tp1\tpeaks.narrowPeak\tstub\t1\n2\tp2\tpeaks.narrowPeak\tstub\t1\n' > '${meta.id}.idr_result/replicate_evidence.tsv'
    printf '{"schema_version":"1.0","id":"%s","strategy":"idr","consolidated_peaks":1,"status":"stub"}\n' '${meta.id}' > '${meta.id}.idr_result/statistics.json'
    printf '{"schema_version":"1.0","type":"idr","id":"%s","dataset":"%s","condition":"%s","target":"%s","genome_id":"%s","build":"%s","strategy":"idr","provider":"idr","provider_version":"2.0.4.2","replicates":[{"record_id":"r1","sample_id":"s1"},{"record_id":"r2","sample_id":"s2"}],"artifacts":{"consolidated_peaks":{"available":true,"path":"consolidated_peaks.tsv"},"consolidated_bed":{"available":true,"path":"consolidated_peaks.bed"}},"status":"stub"}\n' \
        '${meta.id}' '${meta.dataset}' '${meta.condition}' '${meta.target}' '${meta.genome_id}' '${meta.genome_id}' > '${meta.id}.idr.manifest.json'
    cp '${meta.id}.idr.manifest.json' '${meta.id}.idr_result/manifest.json'
    printf '{"schema_version":"1.0","id":"%s","process":"IDR_PROVIDER","status":"stub"}\n' '${meta.id}' > '${meta.id}.idr.execution.json'
    printf '"IDR_PROVIDER":\n    idr: stub\n    package: "2.0.4.2"\n    python: stub\n' > '${meta.id}.idr.versions.yml'
    printf '[STUB] IDR statistical provider\n' > '${meta.id}.idr_reports/idr.log'
    printf '{"id":"%s","process":"IDR_PROVIDER","strategy":"idr","status":"stub"}\n' '${meta.id}' > '${meta.id}.idr.done'
    """
}
