# Native ChIP-seq Differential Binding

> **Historical implementation record.** The current contract is documented in
> [Differential Binding API v1](differential_binding_api.md).

Foundation 0.6 implements the orchestration and contracts required to replace
the legacy differential-binding step after later biological validation.

```mermaid
flowchart LR
    C["Consensus manifests + BEDs"] --> P["DB_PREFLIGHT"]
    B["FINAL_BAM manifests"] --> P
    M["Metadata + explicit DB spec"] --> P
    P --> F["PEAK_COUNTING_PROVIDER"]
    F --> FC["FEATURECOUNTS_PEAK: raw matrix"]
    FC --> D["DESEQ2_DB_MODEL"]
    D --> C1["DB_CONTRAST 1"]
    D --> C2["DB_CONTRAST 2..N"]
    C1 --> A["DB_AGGREGATE"]
    C2 --> A
    A --> O["Semantic DB manifest"]
```

## Run

```bash
cp assets/chipseq_db_spec.example.json chipseq_db_spec.json
nextflow run . -profile local --workflow chipseq \
  --chipseq_config /path/to/pipeline_config.sh \
  --chipseq_run_mode differential_binding \
  --chipseq_consensus_method union \
  --chipseq_db_spec chipseq_db_spec.json
```

The schema is `schemas/differential-binding-v1.schema.json`. V1 supports
featureCounts, DESeq2 Wald, `~ condition` or `~ batch + condition`, explicit
condition contrasts and `none`/`minimum_count` filtering. Interactions,
technical records as independent samples, inferred contrasts, count
pre-normalization, ComBat, multimapping, fractional/multiple assignment and IDR
results are rejected.

Both the dedicated mode and `full` require this provider. The former legacy
step is available only from `chipseq-legacy-v1.0.0`.

## Cache behavior

- peak/BAM/count-policy changes invalidate counting and downstream tasks;
- filter/design/model changes invalidate model and contrasts;
- each contrast is an independent task and reuses the fitted model;
- aggregation changes never recompute inference.

An isolated `-resume` stub cached all six boundaries, including two contrast
tasks sharing one model.

## Validation performed

- six pure-Python tests for design, contrasts, biological replication,
  sample/BAM identity, rank-deficient batch and counting contracts;
- JSON/schema syntax validation and Nextflow lint;
- isolated stub with two contrasts;
- top-level `chipseq --chipseq_run_mode differential_binding` stub;
- exact isolated `-resume` with every process cached;
- scheduler-token audit for new native code.

The later reduced top-level Slurm pass executed featureCounts and DESeq2 through
one contrast and final aggregation. The featureCounts 2.0.6 production image
subsequently returned the expected SAF count in Docker certification run
`32368534261`; the clean DESeq2 1.0.1 image had already passed its dedicated
regression. A reviewed biological dataset, legacy statistical comparison and
production benchmark remain pending.
