nextflow.enable.dsl = 2

process CACHE_TUPLE_PROBE {
    tag "task-${task_id}"
    cache 'deep'

    input:
    tuple val(task_id), val(payload)

    output:
    path "cache-probe-${task_id}.txt"

    script:
    """
    printf '%s\n' '${payload}' > cache-probe-${task_id}.txt
    """
}

workflow {
    CACHE_TUPLE_PROBE(Channel.value(tuple(1, 'helixforge-cache-probe-1')))
}
