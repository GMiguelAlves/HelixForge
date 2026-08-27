nextflow.enable.dsl = 2

include { RUN_MANIFEST } from '../../../modules/local/run_manifest/main'

workflow {
    spec = new groovy.json.JsonSlurper().parse(file(params.recovery_spec, checkIfExists: true))
    if (spec.type != 'rnaseq_terminal_recovery_spec' || spec.status != 'ready') {
        error 'Invalid RNA-seq terminal recovery specification.'
    }
    artifacts = spec.artifacts.collect { entry -> file(entry.path, checkIfExists: true) }
    descriptors = spec.artifacts.collect { entry -> entry.descriptor }
    manifests = spec.source_manifests.collect { value -> file(value, checkIfExists: true) }
    run_base64 = groovy.json.JsonOutput.toJson(spec.run).bytes.encodeBase64().toString()
    descriptors_base64 = groovy.json.JsonOutput.toJson(descriptors).bytes.encodeBase64().toString()
    requests = channel.of(tuple(
        spec.meta,
        file(spec.metadata, checkIfExists: true),
        file(spec.reference_manifest, checkIfExists: true),
        file(params.schema_root, checkIfExists: true),
        manifests,
        artifacts,
        file(spec.contrast_spec, checkIfExists: true),
        run_base64,
        descriptors_base64
    ))
    RUN_MANIFEST(requests)
}
