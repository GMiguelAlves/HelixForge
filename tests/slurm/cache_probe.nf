nextflow.enable.dsl = 2

process CACHE_PROBE {
    tag 'stable-input'
    cache 'deep'

    input:
    val payload

    output:
    path 'cache-probe.txt'

    script:
    """
    printf '%s\n' '${payload}' > cache-probe.txt
    """
}

workflow {
    CACHE_PROBE(channel.value('helixforge-cache-probe'))
}
