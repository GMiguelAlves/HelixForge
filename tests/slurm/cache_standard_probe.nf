nextflow.enable.dsl = 2

process CACHE_STANDARD_PROBE {
    tag 'stable-input'
    cache true

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
    CACHE_STANDARD_PROBE(channel.value('helixforge-cache-probe'))
}
