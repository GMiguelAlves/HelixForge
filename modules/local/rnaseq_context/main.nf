process RNASEQ_CONTEXT {
    tag 'rnaseq:context'
    label 'compatibility_adapter'

    cpus 1
    memory 1.GB
    time 30.m
    cache 'deep'
    errorStrategy 'terminate'
    maxRetries 0

    container params.rnaseq_context_container
    conda "${moduleDir}/environment.yml"

    publishDir "${params.outdir}/pipeline_info/native_rnaseq/context",
        mode: 'copy', overwrite: true,
        pattern: '*.{log,yml,done}'

    input:
    path config_file
    val legacy_root
    val meta

    output:
    tuple val(meta), path('rnaseq_context'), emit: artifacts
    tuple val(meta), path('rnaseq.context.log'), emit: reports
    tuple val(meta), path('rnaseq.context.versions.yml'), emit: versions
    tuple val(meta), path('rnaseq.context.done'), emit: status

    script:
    """
    export PROJECT_DIR='${legacy_root}'
    export PIPELINE_CONFIG="\$PWD/${config_file}"
    source "\$PIPELINE_CONFIG"

    metadata=\$(metadata_default)
    [[ -s "\$metadata" ]] || { echo "[ERROR] RNA-seq metadata not found: \$metadata"; exit 2; }

    mkdir -p rnaseq_context
    cp "\$metadata" rnaseq_context/source_metadata.csv
    printf 'key\tvalue\n' > rnaseq_context/settings.tsv
    printf 'METADATA_BASE_DIR\t%s\n' "\$(cd "\$(dirname "\$metadata")" && pwd)" >> rnaseq_context/settings.tsv
    printf 'NATIVE_RUN_MODE\t%s\n' '${params.rnaseq_run_mode}' >> rnaseq_context/settings.tsv
    printf 'NATIVE_ANALYSIS_MODE\t%s\n' '${params.rnaseq_analysis_mode}' >> rnaseq_context/settings.tsv
    for key in \
        PIPELINE_PROJECTS SCRATCH_ROOT ORGANISM_NAME QUANT_METHOD \
        REF_GENOME_FA REF_TRANSCRIPTS_FA REF_GTF REF_GFF3 \
        SALMON_INDEX_DIR STAR_QUANT_INDEX_DIR QUANT_DIR STAR_QUANT_DIR \
        SALMON_KMER_SIZE STAR_GENECOUNT_COLUMN STAR_READ_FILES_COMMAND \
        STAR_EXTRA_ARGS STAR_GTF_GENOME_SA_INDEX_NBASES \
        STAR_LIMIT_GENOME_GENERATE_RAM TRIM_QUALITY TRIM_LENGTH; do
        printf '%s\t%s\n' "\$key" "\${!key:-}" >> rnaseq_context/settings.tsv
    done

    printf '[INFO] metadata=%s\n[INFO] projects=%s\n[INFO] quant_method=%s\n' \
        "\$metadata" "\$PIPELINE_PROJECTS" "\$QUANT_METHOD" | tee rnaseq.context.log
    printf '"%s":\n    bash: %s\n' '${task.process}' "\${BASH_VERSION}" \
        > rnaseq.context.versions.yml
    printf '{"id":"rnaseq.context","process":"%s","status":"complete"}\n' \
        '${task.process}' > rnaseq.context.done
    """

    stub:
    """
    mkdir -p rnaseq_context/fastq rnaseq_context/reference
    printf '@stub/1\nACGTACGT\n+\nFFFFFFFF\n' > rnaseq_context/fastq/stub_RUN1_R1.fastq
    printf '@stub/2\nTGCATGCA\n+\nFFFFFFFF\n' > rnaseq_context/fastq/stub_RUN1_R2.fastq
    printf '>tx_stub\nACGTACGTACGTACGT\n' > rnaseq_context/reference/transcriptome.fa
    printf '>chrStub\nACGTACGTACGTACGT\n' > rnaseq_context/reference/genome.fa
    printf 'chrStub\tstub\ttranscript\t1\t16\t.\t+\t.\tgene_id "gene_stub"; transcript_id "tx_stub";\n' \
        > rnaseq_context/reference/annotation.gtf
    printf 'dataset,sample_id,file_prefix,run_accession,condition,batch,fastq_1,fastq_2\nSTUB,stub,stub,RUN1,control,B1,%s/rnaseq_context/fastq/stub_RUN1_R1.fastq,%s/rnaseq_context/fastq/stub_RUN1_R2.fastq\n' \
        "\$PWD" "\$PWD" > rnaseq_context/source_metadata.csv
    printf 'key\tvalue\n' > rnaseq_context/settings.tsv
    printf 'NATIVE_RUN_MODE\tfull\nNATIVE_ANALYSIS_MODE\tquantification\nPIPELINE_PROJECTS\tSTUB\nSCRATCH_ROOT\t%s/rnaseq_context\nORGANISM_NAME\tstub\nQUANT_METHOD\tsalmon\n' "\$PWD" >> rnaseq_context/settings.tsv
    printf 'REF_GENOME_FA\t%s/rnaseq_context/reference/genome.fa\nREF_TRANSCRIPTS_FA\t%s/rnaseq_context/reference/transcriptome.fa\nREF_GTF\t%s/rnaseq_context/reference/annotation.gtf\nREF_GFF3\t\n' "\$PWD" "\$PWD" "\$PWD" >> rnaseq_context/settings.tsv
    printf 'SALMON_INDEX_DIR\t${params.outdir}/stub/salmon_index\nSTAR_QUANT_INDEX_DIR\t${params.outdir}/stub/star_index\nQUANT_DIR\t${params.outdir}/stub/quants\nSTAR_QUANT_DIR\t${params.outdir}/stub/star_quant\nSALMON_KMER_SIZE\t3\nSTAR_GENECOUNT_COLUMN\tunstranded\nSTAR_READ_FILES_COMMAND\tcat\nSTAR_EXTRA_ARGS\t\nSTAR_GTF_GENOME_SA_INDEX_NBASES\t2\nSTAR_LIMIT_GENOME_GENERATE_RAM\t100000000\nTRIM_QUALITY\t20\nTRIM_LENGTH\t20\n' >> rnaseq_context/settings.tsv
    printf '[STUB] RNA-seq context\n' > rnaseq.context.log
    printf '"RNASEQ_CONTEXT":\n    bash: stub\n' > rnaseq.context.versions.yml
    printf '{"id":"rnaseq.context","process":"RNASEQ_CONTEXT","status":"stub"}\n' > rnaseq.context.done
    """
}
