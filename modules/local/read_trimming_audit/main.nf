process READ_TRIMMING_AUDIT {
    tag "${meta.id}"
    label 'native_module'
    cpus 1
    memory 2.GB
    time 4.h
    cache 'deep'
    errorStrategy 'terminate'
    container params.read_trimming_audit_container
    conda "${moduleDir}/environment.yml"
    publishDir "${params.outdir}/pipeline_info/native_qc/read_trimming", mode: 'copy', overwrite: true,
        pattern: '*.{json,yml,log,done}'

    input:
    tuple val(meta), path(reads), val(policy), path(prior, arity: '0..*'), path(tool_versions, arity: '0..*')

    output:
    tuple val(meta), path(reads), path("${prefix}.manifest.json"), emit: artifacts
    tuple val(meta), path("${prefix}.manifest.json"), emit: manifest
    tuple val(meta), path("${prefix}.log"), emit: reports
    tuple val(meta), path("${prefix}.versions.yml"), emit: versions
    tuple val(meta), path("${prefix}.execution.json"), emit: execution_metadata
    tuple val(meta), path("${prefix}.done"), emit: status

    script:
    prefix = meta.id + (prior ? '.trimming' : '.raw_validation')
    if (prior.size() > 1 || tool_versions.size() > 1) { error 'Trimming audit accepts at most one prior manifest and one versions file' }
    def request = groovy.json.JsonOutput.toJson([meta: meta, policy: policy,
        resources: [cpus: task.cpus, memory_bytes: task.memory.toBytes(), time: task.time.toString()]]).getBytes('UTF-8').encodeBase64().toString()
    def source = file("${moduleDir}/audit_reads.py").text
    def read_args = (reads instanceof List ? reads : [reads]).collect { read -> "'${read}'" }.join(' ')
    def prior_arg = prior ? "--prior '${prior[0]}'" : ''
    def version_arg = tool_versions ? "--versions '${tool_versions[0]}'" : ''
    """
    set -o pipefail
    python - --request-base64 '${request}' --reads ${read_args} ${prior_arg} ${version_arg} \
        --output '${prefix}.manifest.json' --execution '${prefix}.execution.json' \
        2>&1 <<'HF_TRIMMING_AUDIT_PY' | tee '${prefix}.log'
${source}
HF_TRIMMING_AUDIT_PY
    printf '"%s": {python: "%s"}\\n' '${task.process}' "\$(python --version | awk '{print \$2}')" > '${prefix}.versions.yml'
    printf '{"status":"complete"}\\n' > '${prefix}.done'
    """

    stub:
    prefix = meta.id + (prior ? '.trimming' : '.raw_validation')
    """
    printf '{"schema_version":"1.0","type":"%s","id":"%s","dataset":"%s","genome_id":"%s","status":"stub"}\\n' \
        '${prior ? 'read_trimming' : 'read_validation'}' '${prefix}' '${meta.dataset ?: ''}' '${meta.genome_id ?: ''}' > '${prefix}.manifest.json'
    printf '[STUB] FASTQ validation not performed\\n' > '${prefix}.log'
    printf '"READ_TRIMMING_AUDIT": {python: stub}\\n' > '${prefix}.versions.yml'
    printf '{"status":"stub"}\\n' > '${prefix}.execution.json'
    printf '{"status":"stub"}\\n' > '${prefix}.done'
    """
}
