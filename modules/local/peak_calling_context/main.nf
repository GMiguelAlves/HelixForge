process PEAK_CALLING_CONTEXT {
    tag 'chipseq:peak-context'
    label 'native_module'

    cpus 1
    memory 2.GB
    time 30.m
    cache 'deep'
    errorStrategy 'terminate'
    maxRetries 0

    container params.chipseq_metadata_container
    conda "${moduleDir}/environment.yml"

    publishDir "${params.outdir}/pipeline_info/native_chipseq/peak_context",
        mode: 'copy', overwrite: true, pattern: '*.{tsv,json,yml,done,log}'

    input:
    tuple val(meta), path(chipseq_plan), val(spec_base64)

    output:
    tuple val(meta), path('validated_chipseq_plan.tsv'), path('peak_calling_plan.tsv'), emit: artifacts
    tuple val(meta), path('peak_context.json'), path('peak_context.log'), emit: reports
    tuple val(meta), path('peak_context.versions.yml'), emit: versions
    tuple val(meta), path('peak_context.done'), emit: status

    script:
    """
    validate_peak_context.py \
        --plan '${chipseq_plan}' \
        --spec-base64 '${spec_base64}' \
        --validated-plan validated_chipseq_plan.tsv \
        --peak-plan peak_calling_plan.tsv \
        --report peak_context.json \
        2>&1 | tee peak_context.log
    printf '"%s":\n    python: %s\n' '${task.process}' "\$(python3 --version | awk '{print \$2}')" > peak_context.versions.yml
    printf '{"id":"%s","process":"%s","status":"complete"}\n' '${meta.id}' '${task.process}' > peak_context.done
    """

    stub:
    """
    cp '${chipseq_plan}' validated_chipseq_plan.tsv
    awk 'BEGIN{FS=OFS="\t"} NR==1 {for(i=1;i<=NF;i++) col[\$i]=i; print \$0,"peak_id","control_record_id","caller","caller_version","effective_genome_size","cutoff_type","cutoff","q_value","p_value","format","paired_end_handling","duplicate_policy","additional_args","peak_target_dir"; next} \$(col["is_control"])=="false" {record=\$(col["record_id"]); target=\$(col["target"]); control=\$(col["control_id"]); layout=\$(col["layout"]); peak=record"."target".narrow.macs3"; format=(layout=="paired" ? "BAMPE" : "BAM"); handling=(layout=="paired" ? "fragments" : "tags"); print \$0,peak,control,"macs3","3.0.4","16","q_value","0.01","0.01","",format,handling,"all","","${params.outdir}/stub/080-peak-calling"}' \
        '${chipseq_plan}' > peak_calling_plan.tsv
    printf '{"schema_version":"1.0","type":"peak_calling_context","status":"stub","treatments":2}\n' > peak_context.json
    printf '[STUB] Peak Calling context\n' > peak_context.log
    printf '"PEAK_CALLING_CONTEXT":\n    python: stub\n' > peak_context.versions.yml
    printf '{"id":"%s","process":"PEAK_CALLING_CONTEXT","status":"stub"}\n' '${meta.id}' > peak_context.done
    """
}
