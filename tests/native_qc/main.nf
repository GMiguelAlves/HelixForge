nextflow.enable.dsl = 2

include { FASTQC as FASTQC_RAW }     from '../../modules/local/fastqc/main'
include { TRIM_GALORE }              from '../../modules/local/trim_galore/main'
include { FASTQC as FASTQC_TRIMMED } from '../../modules/local/fastqc/main'
include { MERGE_FASTQ }              from '../../modules/local/merge_fastq/main'
include { FASTQC as FASTQC_MERGED }  from '../../modules/local/fastqc/main'
include { MULTIQC }                  from '../../modules/local/multiqc/main'

workflow {
    def input_dir = file(params.input_dir, checkIfExists: true)
    def target_root = file(params.target_root)
    def runs = ['run_a', 'run_b']

    raw_inputs = channel.fromList(
        runs.collectMany { run ->
            ['R1', 'R2'].collect { mate ->
                tuple(
                    [
                        id             : "TEST.sample.${run}.raw.${mate}",
                        dataset        : 'TEST',
                        sample_id      : 'sample',
                        run_accession  : run,
                        phase          : 'raw',
                        project_scratch: target_root.toString(),
                        target_dir     : "${target_root}/fastqc_raw"
                    ],
                    file("${input_dir}/${run}_${mate}.fastq.gz", checkIfExists: true)
                )
            }
        }
    )

    trim_inputs = channel.fromList(
        runs.collect { run ->
            def trimmed_dir = "${target_root}/trimmed_runs"
            tuple(
                [
                    id             : "TEST.sample.${run}.trim_galore",
                    dataset        : 'TEST',
                    sample_id      : 'sample',
                    run_accession  : run,
                    trim_quality   : 20,
                    trim_length    : 20,
                    trimmed_r1     : "${trimmed_dir}/sample_${run}_R1_trimmed.fastq.gz",
                    trimmed_r2     : "${trimmed_dir}/sample_${run}_R2_trimmed.fastq.gz",
                    trimmed_dir    : trimmed_dir,
                    trimmed_r1_name: "sample_${run}_R1_trimmed.fastq.gz",
                    trimmed_r2_name: "sample_${run}_R2_trimmed.fastq.gz",
                    project_scratch: target_root.toString()
                ],
                file("${input_dir}/${run}_R1.fastq.gz", checkIfExists: true),
                file("${input_dir}/${run}_R2.fastq.gz", checkIfExists: true)
            )
        }
    )

    FASTQC_RAW(raw_inputs)
    TRIM_GALORE(trim_inputs)

    trimmed_fastqc_inputs = TRIM_GALORE.out.artifacts.flatMap { meta, r1, r2 ->
        [
            tuple(meta + [id: "TEST.sample.${meta.run_accession}.trimmed.R1", phase: 'trimmed', target_dir: "${target_root}/fastqc_trimmed_runs"], r1),
            tuple(meta + [id: "TEST.sample.${meta.run_accession}.trimmed.R2", phase: 'trimmed', target_dir: "${target_root}/fastqc_trimmed_runs"], r2)
        ]
    }
    FASTQC_TRIMMED(trimmed_fastqc_inputs)

    merge_inputs = TRIM_GALORE.out.artifacts
        .map { meta, r1, r2 -> tuple('sample', tuple(meta, r1, r2)) }
        .groupTuple()
        .map { sample_id, records ->
            def ordered = records.sort { left, right -> left[0].run_accession <=> right[0].run_accession }
            tuple(
                [
                    id             : 'TEST.sample.merge',
                    dataset        : 'TEST',
                    sample_id      : sample_id,
                    project_scratch: target_root.toString(),
                    target_dir     : "${target_root}/trimmed_merged",
                    output_r1      : "${target_root}/trimmed_merged/sample_R1_trimmed.fastq.gz",
                    output_r2      : "${target_root}/trimmed_merged/sample_R2_trimmed.fastq.gz",
                    output_r1_name : 'sample_R1_trimmed.fastq.gz',
                    output_r2_name : 'sample_R2_trimmed.fastq.gz'
                ],
                ordered.collect { record -> record[1] },
                ordered.collect { record -> record[2] }
            )
        }
    MERGE_FASTQ(merge_inputs)

    merged_fastqc_inputs = MERGE_FASTQ.out.artifacts.flatMap { meta, r1, r2 ->
        [
            tuple(meta + [id: 'TEST.sample.merged.R1', phase: 'merged', target_dir: "${target_root}/fastqc_merged"], r1),
            tuple(meta + [id: 'TEST.sample.merged.R2', phase: 'merged', target_dir: "${target_root}/fastqc_merged"], r2)
        ]
    }
    FASTQC_MERGED(merged_fastqc_inputs)

    multiqc_inputs = FASTQC_RAW.out.artifacts
        .mix(FASTQC_TRIMMED.out.artifacts)
        .mix(FASTQC_MERGED.out.artifacts)
        .map { _meta, artifact -> artifact }
        .collect()
        .map { artifacts ->
            tuple(
                [
                    id         : 'TEST.multiqc',
                    dataset    : 'TEST',
                    report_name: 'TEST_multiqc_030.html',
                    target_dir : "${target_root}/multiqc_030"
                ],
                artifacts
            )
        }
    MULTIQC(multiqc_inputs)
}
