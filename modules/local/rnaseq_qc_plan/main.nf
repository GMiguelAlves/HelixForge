process RNASEQ_QC_PLAN {
    tag 'rnaseq:qc-plan'
    label 'compatibility_adapter'

    cpus 1
    memory 4.GB
    time 1.h
    cache true
    errorStrategy 'terminate'
    maxRetries 0

    publishDir "${params.outdir}/pipeline_info/native_trim_galore/plans",
        mode: 'copy', overwrite: true

    input:
    path config_file
    path plan_annotator
    val legacy_root
    val download_status
    val metadata_status

    output:
    path '*_qc_plan.csv', emit: plans
    path 'rnaseq.qc_plan.log', emit: log
    path 'stub_input_*.fastq', optional: true, emit: stub_reads

    script:
    """
    export PROJECT_DIR='${legacy_root}'
    export PIPELINE_CONFIG="\$PWD/${config_file}"
    source "\$PIPELINE_CONFIG"

    require_pipeline_projects
    metadata=\$(metadata_default)
    python_bin=\${PYTHON_BIN:-python3}
    command -v "\$python_bin" >/dev/null 2>&1

    while IFS= read -r project; do
        "\$python_bin" '${legacy_root}/scripts/030-qc-fastq/generate_qc_plan.py' \
            --metadata "\$metadata" \
            --project "\$project" \
            --scratch-root "\$SCRATCH_ROOT" \
            --output "\${project}_qc_plan.csv"
        "\$python_bin" "\$PWD/${plan_annotator}" \
            --plan "\${project}_qc_plan.csv" \
            --quality "\$TRIM_QUALITY" \
            --length "\$TRIM_LENGTH"
    done < <(pipeline_projects) 2>&1 | tee rnaseq.qc_plan.log
    """

    stub:
    """
    printf '@stub/1\nACGT\n+\nIIII\n' > stub_input_R1.fastq
    printf '@stub/2\nTGCA\n+\nIIII\n' > stub_input_R2.fastq
    printf '%s\n%s\n' \
        'dataset,sample_id,file_prefix,run_accession,raw_r1,raw_r2,trimmed_run_r1,trimmed_run_r2,merged_sample_r1,merged_sample_r2,trim_quality,trim_length' \
        'STUB,stub_sample,stub_sample,stub_run,'"\$PWD"'/stub_input_R1.fastq,'"\$PWD"'/stub_input_R2.fastq,${params.outdir}/stub/trimmed_runs/stub_sample_stub_run_R1_trimmed.fastq.gz,${params.outdir}/stub/trimmed_runs/stub_sample_stub_run_R2_trimmed.fastq.gz,${params.outdir}/stub/trimmed_merged/stub_sample_R1_trimmed.fastq.gz,${params.outdir}/stub/trimmed_merged/stub_sample_R2_trimmed.fastq.gz,20,20' \
        > stub_qc_plan.csv
    printf '[STUB] RNA-seq QC plan\n' > rnaseq.qc_plan.log
    """
}
