process DB_PREFLIGHT {
    tag "${meta.id}"
    label 'native_module'
    label 'db_low'

    cpus 1
    memory 2.GB
    time 30.m
    cache 'deep'
    errorStrategy 'terminate'
    maxRetries 0

    container params.db_adapter_container
    conda "${moduleDir}/environment.yml"

    publishDir "${params.outdir}/pipeline_info/native_chipseq/differential_binding/preflight",
        mode: 'copy', overwrite: true, pattern: '*.{json,yml,tsv,done}'

    input:
    tuple val(meta), path(consensus_dirs), path(consensus_manifests), path(final_bams), path(final_bais),
        path(bam_manifests), path(peak_plan), path(db_spec)

    output:
    tuple val(meta), path('analysis_requests'), path('peak_universes'), path('sample_tables'),
        path('count_specs'), path('model_specs'), path('contrast_specs'), path(db_spec), emit: artifacts
    tuple val(meta), path('db_preflight_report.json'), path('db_preflight_summary.tsv'), emit: reports
    tuple val(meta), path('db_preflight.versions.yml'), emit: versions
    tuple val(meta), path('db_preflight.done'), emit: status

    script:
    def consensusDirArgs = consensus_dirs.collect { directory -> "--consensus-dir '${directory}'" }.join(' ')
    def consensusManifestArgs = consensus_manifests.collect { manifest -> "--consensus-manifest '${manifest}'" }.join(' ')
    def bamArgs = final_bams.collect { bam -> "--bam '${bam}'" }.join(' ')
    def baiArgs = final_bais.collect { bai -> "--bai '${bai}'" }.join(' ')
    def bamManifestArgs = bam_manifests.collect { manifest -> "--bam-manifest '${manifest}'" }.join(' ')
    """
    db_preflight.py \
        ${consensusDirArgs} \
        ${consensusManifestArgs} \
        ${bamArgs} \
        ${baiArgs} \
        ${bamManifestArgs} \
        --peak-plan '${peak_plan}' \
        --spec '${db_spec}' \
        --output-dir . \
        > db_preflight_report.json
    printf '"DB_PREFLIGHT":\n    python: "%s"\n' "\$(python3 --version | awk '{print \$2}')" > db_preflight.versions.yml
    printf '{"id":"%s","process":"DB_PREFLIGHT","status":"complete"}\n' '${meta.id}' > db_preflight.done
    """

    stub:
    """
    mkdir -p analysis_requests peak_universes sample_tables count_specs model_specs contrast_specs
    printf 'stub.condition.peak.000001\tchrStub\t4\t12\n' > peak_universes/stub.condition.bed
    printf 'sample_id\trecord_id\tcondition\tbiological_replicate\ttechnical_replicate\tbatch\tlayout\nS1\tR1\tcontrol\t1\t1\tB1\tpaired\nS2\tR2\ttreated\t1\t1\tB1\tpaired\n' > sample_tables/stub.condition.tsv
    printf '%s\n' '{"schema_version":"1.0","analysis_id":"stub.condition","provider":"featurecounts","genome_id":"stub","peak_type":"narrow","counting":{"provider":"featurecounts","unit":"fragments","min_mapq":0,"strandedness":0,"overlap_policy":"any","allow_multi_overlap":false,"allow_multimapping":false,"fractional":false},"samples":[{"sample_id":"S1","record_id":"R1","condition":"control","biological_replicate":"1","layout":"paired","bam_file":"R1.filtered.bam","bai_file":"R1.filtered.bam.bai"},{"sample_id":"S2","record_id":"R2","condition":"treated","biological_replicate":"1","layout":"paired","bam_file":"R2.filtered.bam","bai_file":"R2.filtered.bam.bai"}]}' > count_specs/stub.condition.json
    printf '%s\n' '{"schema_version":"1.0","analysis_id":"stub.condition","model_id":"stub.condition.deseq2","provider":"deseq2","test":"wald","design":{"formula":"~ condition","variable":"condition","covariates":[]},"filter":{"method":"none"},"normalization":"deseq2_median_of_ratios","parameters":{"alpha":0.05,"lfc_threshold":0,"min_replicates":2}}' > model_specs/stub.condition.json
    printf '%s\n' '{"analysis_id":"stub.condition","model_id":"stub.condition.deseq2","id":"treated_vs_control","factor":"condition","numerator":"treated","denominator":"control","alpha":0.05,"lfc_threshold":0,"order":1}' > contrast_specs/stub.condition--treated_vs_control.json
    printf '%s\n' '{"schema_version":"1.0","type":"differential_binding_request","analysis_id":"stub.condition","peak_bed":"stub.condition.bed","sample_table":"stub.condition.tsv","count_spec":"stub.condition.json","model_spec":"stub.condition.json","status":"stub"}' > analysis_requests/stub.condition.json
    printf 'analysis_id\ttarget\tgenome_id\tpeak_type\tconditions\tsamples\tpeaks\tcontrasts\tstatus\nstub.condition\tH3K27ac\tstub\tnarrow\tcontrol,treated\t2\t1\t1\tstub\n' > db_preflight_summary.tsv
    printf '{"status":"stub","analyses":1,"contrasts":1}\n' > db_preflight_report.json
    printf '"DB_PREFLIGHT":\n    python: stub\n' > db_preflight.versions.yml
    printf '{"id":"%s","process":"DB_PREFLIGHT","status":"stub"}\n' '${meta.id}' > db_preflight.done
    """
}
