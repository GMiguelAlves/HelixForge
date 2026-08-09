process CONSENSUS_INTERVALS {
    tag "${meta.id}:${strategy}"
    label 'native_module'
    label 'consensus'

    cpus 2
    memory 4.GB
    time 2.h
    queue { params.consensus_queue ?: null }
    cache 'deep'
    errorStrategy { task.exitStatus in 130..145 ? 'retry' : 'terminate' }
    maxRetries 2

    container { workflow.containerEngine in ['singularity', 'apptainer'] ? params.consensus_apptainer_container : params.consensus_container }
    conda "${moduleDir}/environment.yml"

    publishDir "${params.outdir}/pipeline_info/native_chipseq/consensus/providers",
        mode: 'copy', overwrite: true, pattern: '*.{json,yml,done,consensus_reports}'
    publishDir { "${params.outdir}/chipseq/consensus/${meta.id}" },
        mode: 'copy', overwrite: true, pattern: '*.consensus_result'

    input:
    tuple val(meta), path(peak_dirs), path(request), val(strategy)

    output:
    tuple val(meta), path("${meta.id}.${strategy}.consensus_result"), emit: artifacts
    tuple val(meta), path("${meta.id}.${strategy}.consensus_reports"), emit: reports
    tuple val(meta), path("${meta.id}.${strategy}.versions.yml"), emit: versions
    tuple val(meta), path("${meta.id}.${strategy}.execution.json"), emit: execution_metadata
    tuple val(meta), path("${meta.id}.${strategy}.manifest.json"), emit: manifest
    tuple val(meta), path("${meta.id}.${strategy}.done"), emit: status

    script:
    def peakDirArgs = peak_dirs.collect { directory -> "--peak-dir '${directory}'" }.join(' ')
    """
    run_consensus.py \
        --request '${request}' \
        ${peakDirArgs} \
        --strategy '${strategy}' \
        --output-dir '${meta.id}.${strategy}.consensus_result' \
        --reports '${meta.id}.${strategy}.consensus_reports' \
        --manifest '${meta.id}.${strategy}.manifest.json' \
        --execution '${meta.id}.${strategy}.execution.json' \
        --versions '${meta.id}.${strategy}.versions.yml' \
        --cpus '${task.cpus}' \
        --memory-bytes '${task.memory.toBytes()}' \
        --task-time '${task.time}' \
        --nextflow-version '${workflow.nextflow.version}' \
        --environment '${workflow.containerEngine ?: 'host'}'
    printf '{"id":"%s","process":"%s","strategy":"%s","status":"complete"}\n' \
        '${meta.id}' '${task.process}' '${strategy}' > '${meta.id}.${strategy}.done'
    """

    stub:
    """
    mkdir -p '${meta.id}.${strategy}.consensus_result' '${meta.id}.${strategy}.consensus_reports'
    printf 'peak_id\tchrom\tstart\tend\tsupport\tsupport_replicates\n%s.%s.000001\tchrStub\t4\t12\t2\t1,2\n' \
        '${meta.id}' '${strategy}' > '${meta.id}.${strategy}.consensus_result/consolidated_peaks.tsv'
    printf 'chrStub\t4\t12\t%s.%s.000001\n' '${meta.id}' '${strategy}' > '${meta.id}.${strategy}.consensus_result/consolidated_peaks.bed'
    printf 'replicate_id\tpeak_id\toriginal_peak_name\tchrom\tstart\tend\tscore\tstrand\tsignal_value\tp_value\tq_value\tsummit\n1\tp1\tp1\tchrStub\t4\t12\t100\t.\t5\t10\t8\t4\n' > '${meta.id}.${strategy}.consensus_result/replicate_evidence.tsv'
    printf '{"schema_version":"1.0","id":"%s","strategy":"%s","consolidated_peaks":1,"status":"stub"}\n' '${meta.id}' '${strategy}' > '${meta.id}.${strategy}.consensus_result/statistics.json'
    printf '{"schema_version":"1.0","type":"consensus","id":"%s","strategy":"%s","status":"stub"}\n' '${meta.id}' '${strategy}' > '${meta.id}.${strategy}.manifest.json'
    cp '${meta.id}.${strategy}.manifest.json' '${meta.id}.${strategy}.consensus_result/manifest.json'
    printf '{"schema_version":"1.0","id":"%s","process":"CONSENSUS_INTERVALS","strategy":"%s","status":"stub"}\n' '${meta.id}' '${strategy}' > '${meta.id}.${strategy}.execution.json'
    printf '"CONSENSUS_INTERVALS":\n    bedtools: stub\n    python: stub\n' > '${meta.id}.${strategy}.versions.yml'
    printf '[STUB] %s\n' '${strategy}' > '${meta.id}.${strategy}.consensus_reports/commands.txt'
    cp '${meta.id}.${strategy}.consensus_result/replicate_evidence.tsv' '${meta.id}.${strategy}.consensus_reports/replicate_evidence.tsv'
    printf '{"id":"%s","process":"CONSENSUS_INTERVALS","strategy":"%s","status":"stub"}\n' '${meta.id}' '${strategy}' > '${meta.id}.${strategy}.done'
    """
}
