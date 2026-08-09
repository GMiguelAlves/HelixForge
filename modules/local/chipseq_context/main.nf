process CHIPSEQ_CONTEXT {
    tag 'chipseq:context'
    label 'compatibility_adapter'

    cpus 1
    memory 1.GB
    time 30.m
    cache 'deep'
    errorStrategy 'terminate'
    maxRetries 0

    container params.chipseq_context_container
    conda "${moduleDir}/environment.yml"

    publishDir "${params.outdir}/pipeline_info/native_chipseq/context",
        mode: 'copy', overwrite: true,
        pattern: '*.{log,yml,done}'

    input:
    path config_file
    val legacy_root
    val meta

    output:
    tuple val(meta), path('chipseq_context'), emit: artifacts
    tuple val(meta), path('chipseq.context.log'), emit: reports
    tuple val(meta), path('chipseq.context.versions.yml'), emit: versions
    tuple val(meta), path('chipseq.context.done'), emit: status

    script:
    """
    export PROJECT_DIR='${legacy_root}'
    export PIPELINE_CONFIG="\$PWD/${config_file}"
    source "\$PIPELINE_CONFIG"

    mkdir -p chipseq_context
    [[ -s "\$METADATA_FILE" ]] || { echo "[ERROR] ChIP-seq metadata not found: \$METADATA_FILE"; exit 2; }
    cp "\$METADATA_FILE" chipseq_context/source_metadata.tsv

    printf 'key\tvalue\n' > chipseq_context/settings.tsv
    printf 'NATIVE_RUN_MODE\t%s\n' '${params.chipseq_run_mode}' >> chipseq_context/settings.tsv
    for key in \
        FASTQ_DIR GENOME_FASTA ANNOTATION_FILE BLACKLIST_BED ORGANISM_NAME \
        OUTPUT_DIR QC_DIR ALIGN_DIR FILTER_DIR REF_DIR ALIGNER BOWTIE2_INDEX_PREFIX \
        BOWTIE2_BUILD_OPTS BOWTIE2_OPTS READ_LAYOUT ALLOW_MISSING_CONTROLS \
        MIN_MAPQ REMOVE_SECONDARY_SUPPLEMENTARY REMOVE_DUPLICATES DEDUP_TOOL \
        THREADS MEMORY SLURM_TIME; do
        printf '%s\t%s\n' "\$key" "\${!key:-}" >> chipseq_context/settings.tsv
    done

    printf '[INFO] metadata=%s\n[INFO] aligner=%s\n[INFO] reference=%s\n' \
        "\$METADATA_FILE" "\$ALIGNER" "\$GENOME_FASTA" | tee chipseq.context.log
    printf '"%s":\n    bash: %s\n' '${task.process}' "\${BASH_VERSION}" \
        > chipseq.context.versions.yml
    printf '{"id":"chipseq.context","process":"%s","status":"complete"}\n' \
        '${task.process}' > chipseq.context.done
    """

    stub:
    """
    mkdir -p chipseq_context/fastq chipseq_context/reference
    for read in \
        input_rep1_R1 input_rep1_R2 \
        chip_rep1_R1 chip_rep1_R2 \
        chip_rep2_R1 chip_rep2_R2; do
        printf '@%s\nACGTACGT\n+\nFFFFFFFF\n' "\$read" > "chipseq_context/fastq/\${read}.fastq"
    done
    printf '>chrStub\nACGTACGTACGTACGT\n' > chipseq_context/reference/genome.fa
    printf 'chrStub\tstub\tgene\t1\t16\t.\t+\t.\tgene_id "stub";\n' \
        > chipseq_context/reference/annotation.gtf
    printf 'chrStub\t4\t8\n' > chipseq_context/reference/blacklist.bed
    printf '%s\n' \
        'sample_id	fastq_1	fastq_2	layout	assay	mark_or_factor	condition	replicate	biological_replicate	technical_replicate	batch	control_id	is_control	organism	genome_id	dataset' \
        'input_rep1	input_rep1_R1.fastq	input_rep1_R2.fastq	paired	input	input	control	1	1	1	batch1		true	stub	stub_v1	STUB' \
        'chip_rep1	chip_rep1_R1.fastq	chip_rep1_R2.fastq	paired	ChIP-seq	H3K27ac	treated	1	1	1	batch1	input_rep1	false	stub	stub_v1	STUB' \
        'chip_rep2	chip_rep2_R1.fastq	chip_rep2_R2.fastq	paired	ChIP-seq	H3K27ac	treated	2	2	1	batch1	input_rep1	false	stub	stub_v1	STUB' \
        > chipseq_context/source_metadata.tsv
    printf 'key\tvalue\nNATIVE_RUN_MODE\talignment\n' > chipseq_context/settings.tsv
    printf 'FASTQ_DIR\t%s/chipseq_context/fastq\n' "\$PWD" >> chipseq_context/settings.tsv
    printf 'GENOME_FASTA\t%s/chipseq_context/reference/genome.fa\n' "\$PWD" >> chipseq_context/settings.tsv
    printf 'ANNOTATION_FILE\t%s/chipseq_context/reference/annotation.gtf\n' "\$PWD" >> chipseq_context/settings.tsv
    printf 'BLACKLIST_BED\t%s/chipseq_context/reference/blacklist.bed\nORGANISM_NAME\tstub\nOUTPUT_DIR\t%s\n' "\$PWD" '${params.outdir}' >> chipseq_context/settings.tsv
    printf 'QC_DIR\t%s/stub/030-qc-fastq\nALIGN_DIR\t%s/stub/050-alignment\nFILTER_DIR\t%s/stub/060-filtering\nREF_DIR\t%s/stub/010-reference\n' \
        '${params.outdir}' '${params.outdir}' '${params.outdir}' '${params.outdir}' >> chipseq_context/settings.tsv
    printf 'ALIGNER\tbowtie2\nBOWTIE2_INDEX_PREFIX\t%s/stub/010-reference/bowtie2/genome\n' '${params.outdir}' >> chipseq_context/settings.tsv
    printf 'BOWTIE2_BUILD_OPTS\t\nBOWTIE2_OPTS\t--very-sensitive\nREAD_LAYOUT\tmetadata\nALLOW_MISSING_CONTROLS\tfalse\nMIN_MAPQ\t30\nREMOVE_SECONDARY_SUPPLEMENTARY\ttrue\nREMOVE_DUPLICATES\ttrue\nDEDUP_TOOL\tsamtools\nTHREADS\t1\nMEMORY\t1G\nSLURM_TIME\t00:05:00\n' \
        >> chipseq_context/settings.tsv
    printf '[STUB] ChIP-seq context\n' > chipseq.context.log
    printf '"CHIPSEQ_CONTEXT":\n    bash: stub\n' > chipseq.context.versions.yml
    printf '{"id":"chipseq.context","process":"CHIPSEQ_CONTEXT","status":"stub"}\n' > chipseq.context.done
    """
}
