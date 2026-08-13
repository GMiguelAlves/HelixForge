process RNASEQ_METADATA {
    tag 'rnaseq:metadata'
    label 'native_module'

    cpus 1
    memory 2.GB
    time 1.h
    cache 'deep'
    errorStrategy 'terminate'
    maxRetries 0

    container params.rnaseq_metadata_container
    conda "${moduleDir}/environment.yml"

    publishDir "${params.outdir}/pipeline_info/native_rnaseq/metadata",
        mode: 'copy', overwrite: true,
        pattern: '*.{csv,tsv,json,yml,done,log}'

    input:
    tuple val(meta), path(context_dir)

    output:
    tuple val(meta), path('*_qc_plan.csv'), emit: artifacts
    tuple val(meta), path('reference_plan.tsv'), emit: references
    tuple val(meta), path('validated_metadata.csv'), path('metadata_validation.json'), path('rnaseq.metadata.log'), emit: reports
    tuple val(meta), path('rnaseq.metadata.versions.yml'), emit: versions
    tuple val(meta), path('rnaseq.metadata.done'), emit: status
    path 'stub_input_*.fastq', optional: true, emit: stub_reads

    script:
    def quality = params.rnaseq_trim_quality == null ? '' : params.rnaseq_trim_quality.toString()
    def length = params.rnaseq_trim_length == null ? '' : params.rnaseq_trim_length.toString()
    """
    python '${moduleDir}/validate_rnaseq_metadata.py' \
        --metadata '${context_dir}/source_metadata.csv' \
        --settings '${context_dir}/settings.tsv' \
        --normalized validated_metadata.csv \
        --plan-dir . \
        --reference-plan reference_plan.tsv \
        --report metadata_validation.json \
        --run-mode '${params.rnaseq_run_mode}' \
        --trim-quality '${quality}' \
        --trim-length '${length}' \
        2>&1 | tee rnaseq.metadata.log

    printf '"%s":\n    python: %s\n' '${task.process}' "\$(python --version 2>&1 | awk '{print \$2}')" \
        > rnaseq.metadata.versions.yml
    printf '{"id":"%s","process":"%s","status":"complete"}\n' \
        '${meta.id}' '${task.process}' > rnaseq.metadata.done
    """

    stub:
    """
    printf '@stub/1\nACGT\n+\nIIII\n' > stub_input_R1.fastq
    printf '@stub/2\nTGCA\n+\nIIII\n' > stub_input_R2.fastq
    printf '%s\n%s\n' \
        'dataset,sample_id,file_prefix,run_accession,raw_r1,raw_r2,trimmed_run_r1,trimmed_run_r2,merged_sample_r1,merged_sample_r2,trim_quality,trim_length' \
        'STUB,stub_sample,stub_sample,stub_run,'"\$PWD"'/stub_input_R1.fastq,'"\$PWD"'/stub_input_R2.fastq,${params.outdir}/stub/trimmed_runs/stub_sample_stub_run_R1_trimmed.fastq.gz,${params.outdir}/stub/trimmed_runs/stub_sample_stub_run_R2_trimmed.fastq.gz,${params.outdir}/stub/trimmed_merged/stub_sample_R1_trimmed.fastq.gz,${params.outdir}/stub/trimmed_merged/stub_sample_R2_trimmed.fastq.gz,20,20' \
        > STUB_qc_plan.csv
    printf 'reference_id\torganism\tgenome\ttranscriptome\tannotation\nSTUB\tstub\t%s/rnaseq_context/reference/genome.fa\t%s/rnaseq_context/reference/transcriptome.fa\t%s/rnaseq_context/reference/annotation.gtf\n' \
        "\$PWD/${context_dir}" "\$PWD/${context_dir}" "\$PWD/${context_dir}" > reference_plan.tsv
    printf 'dataset,sample_id,file_prefix,run_accession,condition,batch,fastq_1,fastq_2\nSTUB,stub_sample,stub_sample,stub_run,control,B1,%s/stub_input_R1.fastq,%s/stub_input_R2.fastq\n' "\$PWD" "\$PWD" > validated_metadata.csv
    printf '{"schema_version":"1.0","status":"stub","rows":1,"biological_samples":1}\n' > metadata_validation.json
    printf '[STUB] RNA-seq metadata\n' > rnaseq.metadata.log
    printf '"RNASEQ_METADATA":\n    python: stub\n' > rnaseq.metadata.versions.yml
    printf '{"id":"%s","process":"RNASEQ_METADATA","status":"stub"}\n' '${meta.id}' > rnaseq.metadata.done
    """
}
