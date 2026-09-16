nextflow.enable.dsl = 2

params.tasks = 1

process CACHE_SCALE_PROBE {
    tag "task-${task_id}"
    cache 'deep'

    input:
    val task_id

    output:
    path "cache-probe-${task_id}.txt"

    script:
    """
    printf '%s\n' 'helixforge-cache-probe-${task_id}' > cache-probe-${task_id}.txt
    """
}

workflow {
    task_count = params.tasks as int
    if (task_count < 1) {
        error "--tasks must be at least 1"
    }
    inputs = Channel
        .fromList((1..task_count).toList())
    CACHE_SCALE_PROBE(inputs)
}
