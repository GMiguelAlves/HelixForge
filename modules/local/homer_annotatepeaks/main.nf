process HOMER_ANNOTATEPEAKS {
    tag "${meta.id}"
    label 'native_module'
    label 'peak_annotation_low'
    cpus 1
    memory 4.GB
    time 1.h
    cache 'deep'
    errorStrategy { task.exitStatus in [137, 143] ? 'retry' : 'terminate' }
    maxRetries 2
    container params.homer_container
    conda "${moduleDir}/environment.yml"
    publishDir "${params.outdir}/chipseq/peak_annotation/homer", mode: 'copy', pattern: '*.homer'

    input:
    tuple val(meta), path(peaks), path(reference), path(annotation), path(request)

    output:
    tuple val(meta), path("${meta.id}.homer"), emit: artifacts
    tuple val(meta), path("${meta.id}.homer/homer.log"), emit: reports
    tuple val(meta), path("${meta.id}.homer/versions.yml"), emit: versions
    tuple val(meta), path("${meta.id}.homer/status.json"), emit: status

    script:
    """
    set -euo pipefail
    started=\$(date +%s)
    mkdir '${meta.id}.homer'
    homer_path=\$(command -v annotatePeaks.pl)
    homer_prefix=\$(dirname "\$(dirname "\$homer_path")")
    # HOMER has no reliable --version switch. Require package metadata rather
    # than inferring a version from the executable name or reporting a guess.
    package_files=("\$homer_prefix"/conda-meta/homer-4.11-*.json)
    test "\${#package_files[@]}" -eq 1 && test -f "\${package_files[0]}"
    cp "\${package_files[0]}" '${meta.id}.homer/homer.package.json'
    sha256sum "\$homer_path" > '${meta.id}.homer/homer.executable.sha256'
    sha256sum "\$(command -v parseGTF.pl)" >> '${meta.id}.homer/homer.executable.sha256'
    printf '%s\n' 'annotatePeaks.pl ${peaks} ${reference} -gid -gtf ${annotation} -cpu ${task.cpus}' > '${meta.id}.homer/command.txt'
    printf '%s\n' 'parseGTF.pl ${annotation} tss -gid' >> '${meta.id}.homer/command.txt'
    parseGTF.pl '${annotation}' tss -gid > '${meta.id}.homer/reference_tss.tsv' 2> '${meta.id}.homer/reference_tss.log'
    annotation_sha=\$(sha256sum '${annotation}' | cut -d ' ' -f 1)
    tss_sha=\$(sha256sum '${meta.id}.homer/reference_tss.tsv' | cut -d ' ' -f 1)
    printf '{"provider":"homer_4_11","annotation_sha256":"%s","tss_sha256":"%s"}\n' \
        "\$annotation_sha" "\$tss_sha" > '${meta.id}.homer/reference_tss.metadata.json'
    if test -s '${peaks}'; then
        annotatePeaks.pl '${peaks}' '${reference}' -gid -gtf '${annotation}' -cpu '${task.cpus}' \
            > '${meta.id}.homer/annotatePeaks.txt' 2> '${meta.id}.homer/homer.log'
    else
        printf 'PeakID\tAnnotation\tDistance to TSS\tNearest PromoterID\n' > '${meta.id}.homer/annotatePeaks.txt'
        printf 'Empty input; HOMER not invoked.\n' > '${meta.id}.homer/homer.log'
    fi
    printf '"HOMER_ANNOTATEPEAKS":\n    homer: "4.11"\n' > '${meta.id}.homer/versions.yml'
    printf '{"process":"HOMER_ANNOTATEPEAKS","cpus":%s,"memory_bytes":%s,"started_epoch":%s,"ended_epoch":%s}\n' \
        '${task.cpus}' '${task.memory.toBytes()}' "\$started" "\$(date +%s)" > '${meta.id}.homer/execution.json'
    printf '{"id":"%s","process":"HOMER_ANNOTATEPEAKS","status":"complete"}\n' '${meta.id}' > '${meta.id}.homer/status.json'
    """

    stub:
    """
    mkdir '${meta.id}.homer'
    printf 'PeakID\tAnnotation\tDistance to TSS\tNearest PromoterID\npeak_stub\tpromoter-TSS\t0\tgene_stub\n' > '${meta.id}.homer/annotatePeaks.txt'
    printf '[STUB]\n' > '${meta.id}.homer/homer.log'
    printf '"HOMER_ANNOTATEPEAKS":\n    homer: stub\n' > '${meta.id}.homer/versions.yml'
    printf '{"id":"%s","process":"HOMER_ANNOTATEPEAKS","status":"stub"}\n' '${meta.id}' > '${meta.id}.homer/status.json'
    """
}
