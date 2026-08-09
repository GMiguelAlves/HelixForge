process CHIPSEQ_METADATA {
    tag 'chipseq:metadata'
    label 'native_module'

    cpus 1
    memory 2.GB
    time 1.h
    cache 'deep'
    errorStrategy 'terminate'
    maxRetries 0

    container params.chipseq_metadata_container
    conda "${moduleDir}/environment.yml"

    publishDir "${params.outdir}/pipeline_info/native_chipseq/metadata",
        mode: 'copy', overwrite: true,
        pattern: '*.{tsv,json,yml,done,log}'

    input:
    tuple val(meta), path(context_dir)

    output:
    tuple val(meta), path('chipseq_plan.tsv'), emit: artifacts
    tuple val(meta), path('validated_metadata.tsv'), path('control_map.tsv'), path('metadata_validation.json'), path('chipseq.metadata.log'), emit: reports
    tuple val(meta), path('chipseq.metadata.versions.yml'), emit: versions
    tuple val(meta), path('chipseq.metadata.done'), emit: status

    script:
    """
    python '${moduleDir}/validate_chipseq_metadata.py' \
        --metadata '${context_dir}/source_metadata.tsv' \
        --settings '${context_dir}/settings.tsv' \
        --normalized validated_metadata.tsv \
        --plan chipseq_plan.tsv \
        --controls control_map.tsv \
        --report metadata_validation.json \
        2>&1 | tee chipseq.metadata.log

    printf '"%s":\n    python: %s\n' '${task.process}' "\$(python --version 2>&1 | awk '{print \$2}')" \
        > chipseq.metadata.versions.yml
    printf '{"id":"%s","process":"%s","status":"complete"}\n' \
        '${meta.id}' '${task.process}' > chipseq.metadata.done
    """

    stub:
    """
    printf '%s\n' \
        'record_id	sample_id	run_accession	dataset	condition	biological_replicate	technical_replicate	layout	single_end	is_control	control_id	target	antibody	genome_id	organism	fastq_1	fastq_2	genome_fasta	annotation_file	blacklist_bed	qc_dir	align_dir	filter_dir	index_prefix	bowtie2_build_opts	bowtie2_opts	min_mapq	remove_secondary_supplementary	remove_duplicates	dedup_tool' \
        'input_rep1	input_rep1		STUB	control	1	1	paired	false	true		input		stub_v1	stub	'"\$PWD"'/${context_dir}/fastq/input_rep1_R1.fastq	'"\$PWD"'/${context_dir}/fastq/input_rep1_R2.fastq	'"\$PWD"'/${context_dir}/reference/genome.fa	'"\$PWD"'/${context_dir}/reference/annotation.gtf	'"\$PWD"'/${context_dir}/reference/blacklist.bed	${params.outdir}/stub/030-qc-fastq	${params.outdir}/stub/050-alignment	${params.outdir}/stub/060-filtering	${params.outdir}/stub/010-reference/bowtie2/genome		--very-sensitive	30	true	true	samtools' \
        'chip_rep1	chip_rep1		STUB	treated	1	1	paired	false	false	input_rep1	H3K27ac		stub_v1	stub	'"\$PWD"'/${context_dir}/fastq/chip_rep1_R1.fastq	'"\$PWD"'/${context_dir}/fastq/chip_rep1_R2.fastq	'"\$PWD"'/${context_dir}/reference/genome.fa	'"\$PWD"'/${context_dir}/reference/annotation.gtf	'"\$PWD"'/${context_dir}/reference/blacklist.bed	${params.outdir}/stub/030-qc-fastq	${params.outdir}/stub/050-alignment	${params.outdir}/stub/060-filtering	${params.outdir}/stub/010-reference/bowtie2/genome		--very-sensitive	30	true	true	samtools' \
        'chip_rep2	chip_rep2		STUB	treated	2	1	paired	false	false	input_rep1	H3K27ac		stub_v1	stub	'"\$PWD"'/${context_dir}/fastq/chip_rep2_R1.fastq	'"\$PWD"'/${context_dir}/fastq/chip_rep2_R2.fastq	'"\$PWD"'/${context_dir}/reference/genome.fa	'"\$PWD"'/${context_dir}/reference/annotation.gtf	'"\$PWD"'/${context_dir}/reference/blacklist.bed	${params.outdir}/stub/030-qc-fastq	${params.outdir}/stub/050-alignment	${params.outdir}/stub/060-filtering	${params.outdir}/stub/010-reference/bowtie2/genome		--very-sensitive	30	true	true	samtools' \
        > chipseq_plan.tsv
    awk 'BEGIN{OFS="\t"} NR==1 {print \$0,"peak_dir","peak_caller","peak_type","macs_qvalue","macs_pvalue","macs_genome_size","macs_extra_opts"; next} {print \$0,"${params.outdir}/stub/080-peak-calling","macs3","narrow","0.01","","16",""}' \
        chipseq_plan.tsv > chipseq_plan.extended.tsv
    mv chipseq_plan.extended.tsv chipseq_plan.tsv
    cp '${context_dir}/source_metadata.tsv' validated_metadata.tsv
    printf 'record_id\tsample_id\tcontrol_id\tcandidate_records\nchip_rep1\tchip_rep1\tinput_rep1\tinput_rep1\nchip_rep2\tchip_rep2\tinput_rep1\tinput_rep1\n' > control_map.tsv
    printf '{"status":"stub","records":3,"controls":1,"ip_records":2}\n' > metadata_validation.json
    printf '[STUB] ChIP-seq metadata\n' > chipseq.metadata.log
    printf '"CHIPSEQ_METADATA":\n    python: stub\n' > chipseq.metadata.versions.yml
    printf '{"id":"%s","process":"CHIPSEQ_METADATA","status":"stub"}\n' '${meta.id}' > chipseq.metadata.done
    """
}
