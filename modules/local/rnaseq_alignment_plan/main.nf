process RNASEQ_ALIGNMENT_PLAN {
    tag 'rnaseq:alignment-plan'
    label 'compatibility_adapter'

    cpus 1
    memory 4.GB
    time 1.h
    cache 'deep'
    errorStrategy 'terminate'
    maxRetries 0

    publishDir "${params.outdir}/pipeline_info/native_alignment/plans",
        mode: 'copy', overwrite: true,
        pattern: '*.{csv,tsv,log}'

    input:
    path config_file
    val legacy_root
    path qc_plan
    val reference_status
    val qc_status

    output:
    path '*.alignment_settings.tsv', emit: settings
    path '*_star_plan.csv', optional: true, emit: plans
    path 'rnaseq.alignment_plan.log', emit: log
    path 'stub_reference.fa', optional: true, emit: stub_reference
    path 'stub_annotation.gtf', optional: true, emit: stub_annotation

    script:
    """
    export PROJECT_DIR='${legacy_root}'
    export PIPELINE_CONFIG="\$PWD/${config_file}"
    source "\$PIPELINE_CONFIG"
    activate_python_env

    project=\$(python -c "import csv,sys; print(next(csv.DictReader(open(sys.argv[1], newline='')))['dataset'])" '${qc_plan}')
    settings="\${project}.alignment_settings.tsv"
    printf 'method\tproject\treference\tannotation\tindex_dir\toutput_root\tread_files_command\textra_args\tgenome_sa_index_nbases\tlimit_genome_generate_ram\n' \
        > "\$settings"
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
        "\$QUANT_METHOD" "\$project" "\$REF_GENOME_FA" "\$REF_GTF" \
        "\$STAR_QUANT_INDEX_DIR" "\$STAR_QUANT_DIR" \
        "\$STAR_READ_FILES_COMMAND" "\$STAR_EXTRA_ARGS" \
        "\$STAR_GTF_GENOME_SA_INDEX_NBASES" "\$STAR_LIMIT_GENOME_GENERATE_RAM" \
        >> "\$settings"

    if [[ "\$QUANT_METHOD" == 'star' ]]; then
        [[ -s "\$REF_GENOME_FA" ]] || { echo "[ERRO] Reference genome ausente: \$REF_GENOME_FA"; exit 1; }
        [[ -s "\$REF_GTF" ]] || { echo "[ERRO] Annotation GTF ausente: \$REF_GTF"; exit 1; }
        python '${legacy_root}/scripts/040-alignment/generate_star_plan.py' \
            --qc-plan '${qc_plan}' \
            --project "\$project" \
            --output-root "\$STAR_QUANT_DIR" \
            --output "\${project}_star_plan.csv"
    fi 2>&1 | tee rnaseq.alignment_plan.log
    """

    stub:
    """
    printf '>chrStub\nACGTACGTACGTACGT\n' > stub_reference.fa
    printf 'chrStub\tstub\tgene\t1\t16\t.\t+\t.\tgene_id "gene_stub";\n' > stub_annotation.gtf
    printf 'method\tproject\treference\tannotation\tindex_dir\toutput_root\tread_files_command\textra_args\tgenome_sa_index_nbases\tlimit_genome_generate_ram\n' \
        > STUB.alignment_settings.tsv
    printf 'star\tSTUB\t%s/stub_reference.fa\t%s/stub_annotation.gtf\t%s/stub/star_index_gtf\t%s/stub/star_quant\tcat\t\t2\t100000000\n' \
        "\$PWD" "\$PWD" '${params.outdir}' '${params.outdir}' \
        >> STUB.alignment_settings.tsv
    printf '%s\n%s\n' \
        'dataset,sample_id,num_runs,merged_sample_r1,merged_sample_r2,star_dir,counts_file,bam_file,log_file' \
        'STUB,stub_sample,1,${params.outdir}/stub/trimmed_merged/stub_sample_R1_trimmed.fastq.gz,${params.outdir}/stub/trimmed_merged/stub_sample_R2_trimmed.fastq.gz,${params.outdir}/stub/star_quant/STUB/stub_sample,${params.outdir}/stub/star_quant/STUB/stub_sample/ReadsPerGene.out.tab,${params.outdir}/stub/star_quant/STUB/stub_sample/Aligned.sortedByCoord.out.bam,${params.outdir}/stub/star_quant/STUB/stub_sample/Log.final.out' \
        > STUB_star_plan.csv
    printf '[STUB] RNA-seq alignment plan\n' > rnaseq.alignment_plan.log
    """
}
