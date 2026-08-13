# RNA-seq native foundation validation

Validation date: 2026-08-13  
Validated commit: `97d6c4b`  
Runtime: Nextflow `25.10.7`, Java `21`, Slurm  
Concurrency: `executor.queueSize=5`

## Scope

This controlled pass validates the new RNA-seq orchestration boundary:

```text
local FASTQs + samplesheet
  -> RNASEQ_CONTEXT
  -> RNASEQ_METADATA
  -> REFERENCE_BUNDLE
  -> native QC
  -> Salmon
  -> Import/tximport
  -> DESeq2
  -> compatibility final report
```

The legacy download, metadata, reference, QC-plan, and complete-QC processes
were absent from the executed DAG. `RNASEQ_CONTEXT` remains a temporary adapter
for `pipeline_config.sh`; it does not acquire or modify inputs.

## Results

- Python discovery: 66 tests, all passed.
- JSON schema parse and Python byte compilation: passed.
- Full RNA-seq `-stub-run` on Slurm: passed.
- Nextflow summary: 25 tasks succeeded, 2 cached, duration 1m58s.
- `RNASEQ_METADATA`: executed successfully.
- `REFERENCE_BUNDLE`: executed successfully.
- Production Import policy: `full_length + lengthScaledTPM` accepted.
- Queue was empty after completion.
- Temporary validation directory (13 MB) was removed from
  `/scratch/Schisto-epigenetics/gustavo/`.

The pass detected and resolved two implementation defects before completion:
an invalid dynamic `publishDir` expression and a duplicated path segment in the
Reference Bundle stub fixture.

## Interpretation

This is structural/runtime validation, not scientific regression. Stub outputs
prove DSL2 wiring, contracts, scheduling, stage boundaries, and report/DAG
generation. Real biological validation remains intentionally deferred until
the release-candidate pass with reviewed RNA-seq and ChIP-seq benchmarks.
