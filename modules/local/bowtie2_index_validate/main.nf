process BOWTIE2_INDEX_VALIDATE {
    tag "${meta.id}"
    label 'native_module'
    cpus 1
    memory 2.GB
    time 1.h
    cache 'deep'
    errorStrategy 'terminate'
    container "${workflow.containerEngine in ['singularity', 'apptainer'] ? params.bowtie2_apptainer_container : params.bowtie2_container}"
    conda "${moduleDir}/../bowtie2_index/environment.yml"

    publishDir "${params.outdir}/pipeline_info/native_alignment/bowtie2_index_validate",
        mode: 'copy', overwrite: true, pattern: '*.{json,yml,done,bowtie2_index_reports}'

    input:
    tuple val(meta), path(reference), path(supplied_index, name: 'supplied_index'), path(source_manifest, name: 'source_index.manifest.json'), val(index_params)

    output:
    tuple val(meta), path('bowtie2_index'), emit: artifacts
    tuple val(meta), path("${meta.id}.bowtie2_index_reports"), emit: reports
    tuple val(meta), path("${meta.id}.versions.yml"), emit: versions
    tuple val(meta), path("${meta.id}.execution.json"), emit: execution_metadata
    tuple val(meta), path("${meta.id}.manifest.json"), emit: manifest
    tuple val(meta), path("${meta.id}.bowtie2_index.done"), emit: status

    script:
    def clean_params = [basename: index_params.basename ?: 'genome', extra_args: index_params.extra_args ?: '']
    def request = groovy.json.JsonOutput.toJson([meta: meta, parameters: clean_params,
        resources: [cpus: task.cpus, memory_bytes: task.memory.toBytes(), time: task.time.toString()]]).getBytes('UTF-8').encodeBase64().toString()
    def helper_hash = java.security.MessageDigest.getInstance('SHA-256').digest(file("${moduleDir}/../bowtie2_index/index_bundle.py").bytes).encodeHex().toString()
    def helper_source = file("${moduleDir}/../bowtie2_index/index_bundle.py").text
    """
    # index_bundle.py SHA256: ${helper_hash}
    set -o pipefail
    mkdir -p '${meta.id}.bowtie2_index_reports'
    python3 - validate \
        --index '${supplied_index}' --reference '${reference}' \
        --source-manifest '${source_manifest}' --request-base64 '${request}' \
        --output '${meta.id}.manifest.json' --execution-output '${meta.id}.execution.json' \
        2>&1 <<'HELIXFORGE_INDEX_PY' | tee '${meta.id}.bowtie2_index_reports/validation.log'
${helper_source}
HELIXFORGE_INDEX_PY
    ln -s "\$(readlink -f '${supplied_index}')" bowtie2_index
    printf '"%s":\\n    bowtie2: "%s"\\n' '${task.process}' \
        "\$(bowtie2 --version | sed -n '1s/.*version //p')" > '${meta.id}.versions.yml'
    printf '{"id":"%s","status":"complete","index_source":"prebuilt"}\\n' '${meta.id}' > '${meta.id}.bowtie2_index.done'
    """

    stub:
    """
    mkdir -p bowtie2_index '${meta.id}.bowtie2_index_reports'
    printf '[STUB] validation not performed\\n' > '${meta.id}.bowtie2_index_reports/validation.log'
    printf '{"status":"stub","index_source":"prebuilt"}\\n' > '${meta.id}.manifest.json'
    cp '${meta.id}.manifest.json' '${meta.id}.execution.json'
    printf '"BOWTIE2_INDEX_VALIDATE": {bowtie2: stub}\\n' > '${meta.id}.versions.yml'
    printf '{"status":"stub"}\\n' > '${meta.id}.bowtie2_index.done'
    """
}
