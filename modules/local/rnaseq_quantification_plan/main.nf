process RNASEQ_QUANTIFICATION_PLAN {
    tag 'rnaseq:quantification-plan'
    label 'compatibility_adapter'

    cpus 1
    memory 4.GB
    time 1.h
    cache 'deep'
    errorStrategy 'terminate'
    maxRetries 0

    publishDir "${params.outdir}/pipeline_info/native_quantification/plans",
        mode: 'copy', overwrite: true,
        pattern: '*.{csv,tsv,log}'

    input:
    path config_file
    val pipeline_root
    path qc_plan
    val reference_status
    val qc_status

    output:
    path '*.quantification_settings.tsv', emit: settings
    path '*_salmon_plan.csv', optional: true, emit: plans
    path 'rnaseq.quantification_plan.log', emit: log
    path 'stub_transcriptome.fa', optional: true, emit: stub_transcriptome

    script:
    """
    export PROJECT_DIR='${pipeline_root}'
    export PIPELINE_CONFIG="\$PWD/${config_file}"
    source "\$PIPELINE_CONFIG"
    activate_python_env

    [[ "\$SALMON_KMER_SIZE" =~ ^[0-9]+\$ ]] || { echo '[ERRO] SALMON_KMER_SIZE deve ser inteiro.'; exit 1; }
    (( SALMON_KMER_SIZE >= 1 && SALMON_KMER_SIZE <= 31 && SALMON_KMER_SIZE % 2 == 1 )) || \
        { echo '[ERRO] SALMON_KMER_SIZE deve ser impar entre 1 e 31.'; exit 1; }
    [[ '${params.salmon_lib_type}' =~ ^[A-Za-z]+\$ ]] || { echo '[ERRO] salmon_lib_type invalido.'; exit 1; }

    analysis_mode='${params.rnaseq_analysis_mode}'
    case "\$analysis_mode" in
        config) [[ "\$QUANT_METHOD" == 'salmon' ]] && enabled=true || enabled=false ;;
        quantification|both) enabled=true ;;
        alignment) enabled=false ;;
        *) echo "[ERRO] rnaseq_analysis_mode invalido: \$analysis_mode"; exit 1 ;;
    esac

    project=\$(python -c "import csv,sys; print(next(csv.DictReader(open(sys.argv[1], newline='')))['dataset'])" '${qc_plan}')
    settings="\${project}.quantification_settings.tsv"
    printf 'method\tenabled\tconfigured_method\tproject\ttranscriptome\tindex_dir\toutput_root\tkmer_size\tlib_type\tvalidate_mappings\n' \
        > "\$settings"
    printf 'salmon\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
        "\$enabled" "\$QUANT_METHOD" "\$project" "\$REF_TRANSCRIPTS_FA" \
        "\$SALMON_INDEX_DIR" "\$QUANT_DIR" "\$SALMON_KMER_SIZE" \
        '${params.salmon_lib_type}' '${params.salmon_validate_mappings}' \
        >> "\$settings"

    if [[ "\$enabled" == true ]]; then
        [[ -s "\$REF_TRANSCRIPTS_FA" ]] || { echo "[ERRO] Transcriptome ausente: \$REF_TRANSCRIPTS_FA"; exit 1; }
        python '${moduleDir}/resources/usr/bin/generate_salmon_plan.py' \
            --qc-plan '${qc_plan}' \
            --project "\$project" \
            --output-root "\$QUANT_DIR" \
            --output "\${project}_salmon_plan.csv"
    fi 2>&1 | tee rnaseq.quantification_plan.log
    """

    stub:
    """
    printf '>tx_stub\nACGTACGTACGTACGT\n' > stub_transcriptome.fa
    printf 'method\tenabled\tconfigured_method\tproject\ttranscriptome\tindex_dir\toutput_root\tkmer_size\tlib_type\tvalidate_mappings\n' \
        > STUB.quantification_settings.tsv
    printf 'salmon\ttrue\tsalmon\tSTUB\t%s/stub_transcriptome.fa\t%s/stub/salmon_index\t%s/stub/quants\t3\tA\ttrue\n' \
        "\$PWD" '${params.outdir}' '${params.outdir}' \
        >> STUB.quantification_settings.tsv
    printf '%s\n%s\n' \
        'dataset,sample_id,num_runs,merged_sample_r1,merged_sample_r2,quant_dir' \
        'STUB,stub_sample,1,${params.outdir}/stub/trimmed_merged/stub_sample_R1_trimmed.fastq.gz,${params.outdir}/stub/trimmed_merged/stub_sample_R2_trimmed.fastq.gz,${params.outdir}/stub/quants/STUB/stub_sample' \
        > STUB_salmon_plan.csv
    printf '[STUB] RNA-seq quantification plan\n' > rnaseq.quantification_plan.log
    """
}
