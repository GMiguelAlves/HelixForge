nextflow.enable.dsl = 2


process PREPARE_SYNTHETIC_BROAD {
    tag 'synthetic-broad:reference-truth'
    label 'benchmark_medium'
    cache 'deep'
    errorStrategy 'terminate'
    maxRetries 0

    publishDir "${params.dataset_outdir}", mode: 'copy', overwrite: false, pattern: '{reference,truth}'
    publishDir "${params.dataset_outdir}/provenance", mode: 'copy', overwrite: true, pattern: 'truth_determinism.json'

    input:
    path design_config
    path prepare_script
    path validate_script
    path prepare_common_script
    path validate_common_script

    output:
    path 'reference', emit: reference
    path 'truth', emit: truth
    path 'truth_determinism.json', emit: validation

    script:
    """
    python '${prepare_script}' \
        --config '${design_config}' --output run1
    python '${prepare_script}' \
        --config '${design_config}' --output run2
    python '${validate_script}' truth \
        --config '${design_config}' --primary run1 --repeat run2 \
        --output truth_determinism.json
    mv run1/reference .
    mv run1/truth .
    rm -rf run1 run2
    """
}


process BUILD_MAPPABILITY_INDEX {
    tag 'synthetic-broad:mappability-index'
    label 'benchmark_high'
    cache 'deep'
    errorStrategy 'terminate'
    maxRetries 0

    publishDir "${params.dataset_outdir}/reference/bowtie2", mode: 'copy', overwrite: false

    input:
    path reference

    output:
    path 'bowtie2_index', emit: index
    path 'bowtie2_build.log', emit: log

    script:
    """
    mkdir bowtie2_index
    bowtie2-build --threads ${task.cpus} \
        '${reference}/synthetic_chip_v1.fa' bowtie2_index/genome \
        > bowtie2_build.log 2>&1
    """
}


process VALIDATE_TRUTH_MAPPABILITY {
    tag 'synthetic-broad:truth-mappability'
    label 'benchmark_low'
    cache 'deep'
    errorStrategy 'terminate'
    maxRetries 0

    publishDir "${params.dataset_outdir}/provenance", mode: 'copy', overwrite: true

    input:
    path design_config
    path reference
    path truth
    path bowtie2_index
    path validate_script
    path prepare_script
    path prepare_common_script
    path validate_common_script

    output:
    path 'truth_validation.json', emit: validation
    path 'mappability.log', emit: log

    script:
    """
    bowtie2 -f -x '${bowtie2_index}/genome' \
        -U '${truth}/broad_boundary_mappability_probes.fa' \
        -k 2 --threads ${task.cpus} -S mappability.sam \
        > mappability.log 2>&1
    python '${validate_script}' truth \
        --config '${design_config}' --primary . --repeat . \
        --sam mappability.sam --output truth_validation.json
    """
}


process SIMULATE_CHIPS_LIBRARY {
    tag "synthetic-broad:${sample}"
    label 'benchmark_simulation'
    cache 'deep'
    errorStrategy 'terminate'
    maxRetries 0

    publishDir "${params.dataset_outdir}/fastq", mode: 'link', overwrite: false,
        pattern: 'library/*.fastq', saveAs: { name -> name.tokenize('/')[-1] }
    publishDir "${params.dataset_outdir}/provenance/libraries", mode: 'copy', overwrite: true,
        pattern: 'library/*.{json,log}', saveAs: { name -> name.tokenize('/')[-1] }

    input:
    tuple val(sample), path(reference), path(truth), path(truth_validation)
    path design_config
    path chips_binary
    val chips_source_sha256
    path simulation_script

    output:
    tuple val(sample),
        path("library/${sample}_1.fastq"),
        path("library/${sample}_2.fastq"),
        path("library/${sample}.simulation.json"),
        path("library/${sample}.stdout.log"),
        path("library/${sample}.stderr.log"),
        emit: libraries

    script:
    """
    python '${simulation_script}' \
        --config '${design_config}' \
        --chips '${chips_binary}' \
        --chips-source-sha256 '${chips_source_sha256}' \
        --reference '${reference}/synthetic_chip_v1.fa' \
        --peaks '${truth}/broad_true_domains.bed' \
        --sample '${sample}' --output-dir library
    """
}


process VALIDATE_SYNTHETIC_BROAD_DATASET {
    tag 'synthetic-broad:dataset-validation'
    label 'benchmark_medium'
    cache 'deep'
    errorStrategy 'terminate'
    maxRetries 0

    publishDir "${params.dataset_outdir}/provenance", mode: 'copy', overwrite: true

    input:
    path design_config
    path library_files
    path aggregate_script
    path validate_script
    path prepare_script
    path prepare_common_script
    path validate_common_script

    output:
    path 'simulation_manifest.json', emit: simulation_manifest
    path 'dataset_manifest.json', emit: dataset_manifest

    script:
    def manifestArgs = library_files.findAll { file -> file.name.endsWith('.simulation.json') }
        .collect { file -> "--manifest '${file}'" }.join(' ')
    """
    mkdir fastq
    cp *.fastq fastq/
    python '${aggregate_script}' \
        ${manifestArgs} --output simulation_manifest.json
    python '${validate_script}' dataset \
        --config '${design_config}' --fastq-dir fastq \
        --simulation-manifest simulation_manifest.json \
        --output dataset_manifest.json
    """
}


workflow {
    if (!params.design_config || !params.chips_binary || !params.chips_source_sha256 || !params.dataset_outdir) {
        error 'Required: --design_config, --chips_binary, --chips_source_sha256, --dataset_outdir'
    }
    design_ch = channel.value(file(params.design_config, checkIfExists: true))
    chips_ch = channel.value(file(params.chips_binary, checkIfExists: true))
    prepare_script_ch = channel.value(file("${projectDir}/prepare_synthetic_broad.py", checkIfExists: true))
    validate_script_ch = channel.value(file("${projectDir}/validate_synthetic_broad.py", checkIfExists: true))
    prepare_common_script_ch = channel.value(file("${projectDir}/prepare_synthetic_narrow.py", checkIfExists: true))
    validate_common_script_ch = channel.value(file("${projectDir}/validate_synthetic_narrow.py", checkIfExists: true))
    simulation_script_ch = channel.value(file("${projectDir}/simulate_chips_broad.py", checkIfExists: true))
    aggregate_script_ch = channel.value(file("${projectDir}/../common/aggregate_simulation_manifests.py", checkIfExists: true))

    PREPARE_SYNTHETIC_BROAD(
        design_ch,
        prepare_script_ch,
        validate_script_ch,
        prepare_common_script_ch,
        validate_common_script_ch
    )
    BUILD_MAPPABILITY_INDEX(PREPARE_SYNTHETIC_BROAD.out.reference)
    VALIDATE_TRUTH_MAPPABILITY(
        design_ch,
        PREPARE_SYNTHETIC_BROAD.out.reference,
        PREPARE_SYNTHETIC_BROAD.out.truth,
        BUILD_MAPPABILITY_INDEX.out.index,
        validate_script_ch,
        prepare_script_ch,
        prepare_common_script_ch,
        validate_common_script_ch
    )

    simulation_inputs = channel
        .of('chip_rep1', 'chip_rep2', 'input')
        .combine(PREPARE_SYNTHETIC_BROAD.out.reference)
        .combine(PREPARE_SYNTHETIC_BROAD.out.truth)
        .combine(VALIDATE_TRUTH_MAPPABILITY.out.validation)
    SIMULATE_CHIPS_LIBRARY(simulation_inputs, design_ch, chips_ch, params.chips_source_sha256, simulation_script_ch)

    library_files_ch = SIMULATE_CHIPS_LIBRARY.out.libraries
        .map { _sample, r1, r2, manifest, stdout, stderr -> [r1, r2, manifest, stdout, stderr] }
        .collect()
        .map { files -> files.flatten() }
    VALIDATE_SYNTHETIC_BROAD_DATASET(
        design_ch,
        library_files_ch,
        aggregate_script_ch,
        validate_script_ch,
        prepare_script_ch,
        prepare_common_script_ch,
        validate_common_script_ch
    )
}
