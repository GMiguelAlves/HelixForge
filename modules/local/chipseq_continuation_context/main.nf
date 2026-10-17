process CHIPSEQ_CONTINUATION_CONTEXT {
    tag 'chipseq:continuation'
    label 'native_module'
    cpus 1
    memory 1.GB
    time 2.h
    cache 'deep'
    errorStrategy 'terminate'
    container params.chipseq_metadata_container
    conda "${moduleDir}/environment.yml"
    publishDir "${params.outdir}/pipeline_info/native_chipseq/continuation", mode: 'copy', pattern: '*.{json,log,yml,done}'

    input:
    tuple val(meta), val(request), path(inputs, stageAs: 'inputs??/*')

    output:
    tuple val(meta), path('continuation.plan.json'), path(inputs), emit: artifacts
    tuple val(meta), path('continuation.context.log'), emit: reports
    tuple val(meta), path('continuation.context.versions.yml'), emit: versions
    tuple val(meta), path('continuation.context.done'), emit: status

    script:
    def source = file("${moduleDir}/validate.py").text
    def encoded = groovy.json.JsonOutput.toJson(request).bytes.encodeBase64().toString()
    def paths = groovy.json.JsonOutput.toJson(inputs.collect { path -> path.toString() }).bytes.encodeBase64().toString()
    """
    set -o pipefail
    python3 - --request '${encoded}' --paths '${paths}' <<'HF_CONTINUATION' | tee continuation.context.log
${source}
HF_CONTINUATION
    printf '"CHIPSEQ_CONTINUATION_CONTEXT": {python: "%s"}\\n' "\$(python3 --version | awk '{print \$2}')" > continuation.context.versions.yml
    printf '{"status":"complete"}\\n' > continuation.context.done
    """

    stub:
    def source = file("${moduleDir}/validate.py").text
    def encoded = groovy.json.JsonOutput.toJson(request).bytes.encodeBase64().toString()
    def paths = groovy.json.JsonOutput.toJson(inputs.collect { path -> path.toString() }).bytes.encodeBase64().toString()
    """
    set -o pipefail
    python3 - --request '${encoded}' --paths '${paths}' --stub <<'HF_CONTINUATION' | tee continuation.context.log
${source}
HF_CONTINUATION
    printf '"CHIPSEQ_CONTINUATION_CONTEXT": {python: stub}\\n' > continuation.context.versions.yml
    printf '{"status":"stub"}\\n' > continuation.context.done
    """
}
