include { read_continuation_plan } from '../../subworkflows/local/chipseq/post_consensus'

def is_eager(value) {
    def name = value?.getClass()?.name ?: ''
    if (name.contains('LazyMap') || name.contains('LazyValueMap')) {
        return false
    }
    if (value instanceof Map) return value.values().every { item -> is_eager(item) }
    if (value instanceof List) return value.every { item -> is_eager(item) }
    true
}

workflow {
    plan_file = file(params.plan, checkIfExists: true)
    // Ensure the guard would actually reject the parser that caused the race.
    assert !is_eager(new groovy.json.JsonSlurper().parseText('{"nested":{"id":"x"}}')): 'Regression guard accepted lazy JSON'

    plans = channel.fromList((0..<128).toList()).map { index -> tuple(index, read_continuation_plan(plan_file)) }
    all_reads = channel.empty()
    (0..<8).each { branch ->
        def reads = plans.map { index, plan ->
            assert is_eager(plan): 'Continuation plan contains lazy JSON maps'
            assert plan.peaks*.meta*.artifact_type == [params.expected_kind]
            assert plan.records*.record_id.sort() == ['input', 'ip1', 'ip2']
            assert plan.project.genome_id == 'fixture_v1'
            assert plan.metadata.manifest != null && plan.reference.manifest != null
            tuple(index, branch, plan.peaks[0].meta.id)
        }
        all_reads = all_reads.mix(reads)
    }
    all_reads.toList().view { rows ->
        assert rows.size() == 1024
        assert rows.collect { row -> "${row[0]}:${row[1]}" }.unique().size() == 1024
        assert rows.every { row -> row[2] == params.expected_id }
        "PASS: ${params.expected_kind}; 128 plans, 8 readers, 1024 verified reads"
    }
}
