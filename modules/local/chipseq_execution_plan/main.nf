process CHIPSEQ_EXECUTION_PLAN {
    tag 'chipseq:plan'
    label 'native_module'
    cpus 1
    memory 1.GB
    time 10.m
    cache 'deep'
    errorStrategy 'terminate'
    container params.chipseq_metadata_container
    conda "${moduleDir}/environment.yml"
    publishDir "${params.outdir}/pipeline_info/native_chipseq/plan", mode: 'copy', pattern: '*.{json,log,yml,done}'

    input:
    tuple val(meta), path(metadata), path(db_spec), val(request)

    output:
    tuple val(meta), path(metadata), path('chipseq.execution_plan.json'), emit: artifacts
    tuple val(meta), path('chipseq.execution_plan.json'), emit: manifest
    tuple val(meta), path('chipseq.execution_plan.log'), emit: reports
    tuple val(meta), path('chipseq.execution_plan.versions.yml'), emit: versions
    tuple val(meta), path('chipseq.execution_plan.done'), emit: status

    script:
    def helper = file("${moduleDir}/../db_preflight/resources/usr/bin/db_preflight.py").bytes.encodeBase64().toString()
    def source = file("${moduleDir}/plan.py").text
    def encoded = groovy.json.JsonOutput.toJson(request).bytes.encodeBase64().toString()
    def db_arg = db_spec ? "--db-spec '${db_spec}'" : ''
    """
    set -o pipefail
    python3 - --metadata '${metadata}' --request '${encoded}' --db-helper '${helper}' ${db_arg} <<'HF_PLAN' | tee chipseq.execution_plan.log
${source}
HF_PLAN
    printf '"CHIPSEQ_EXECUTION_PLAN": {python: "%s"}\\n' "\$(python3 --version | awk '{print \$2}')" > chipseq.execution_plan.versions.yml
    printf '{"status":"complete"}\\n' > chipseq.execution_plan.done
    """

    stub:
    def encoded = groovy.json.JsonOutput.toJson(request).bytes.encodeBase64().toString()
    """
    python3 -c 'import json,base64; d=json.loads(base64.b64decode("${encoded}")); d.update(schema_version="1.0",type="chipseq_execution_plan",id="chipseq.execution_plan",status="stub"); json.dump(d,open("chipseq.execution_plan.json","w"))'
    printf '[STUB] Composition not scientifically validated\\n' > chipseq.execution_plan.log
    printf '"CHIPSEQ_EXECUTION_PLAN": {python: stub}\\n' > chipseq.execution_plan.versions.yml
    printf '{"status":"stub"}\\n' > chipseq.execution_plan.done
    """
}
