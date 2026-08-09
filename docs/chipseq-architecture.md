# Native ChIP-seq architecture

The native foundation is deliberately smaller than the legacy workflow. It
establishes stable contracts before filtering and peak-calling policies are
implemented.

```mermaid
flowchart TD
    CFG["Legacy-compatible configuration"] --> CTX["CHIPSEQ_CONTEXT adapter"]
    CTX --> META["CHIPSEQ_METADATA validation"]
    META --> PLAN["Explicit record/control plan"]
    PLAN --> FQ["FASTQC (reused)"]
    FQ --> MQ["MULTIQC (reused)"]
    CTX --> REF["Reference API"]
    REF --> BI["BOWTIE2_INDEX"]
    PLAN --> BA["BOWTIE2_ALIGN"]
    BI --> BA
    BA --> BAM["Sorted BAM + BAI + statistics + manifest"]

    BAM -. future .-> SEL["BAM_SELECT"]
    SEL -. future .-> DUP["BAM_DUPLICATES"]
    DUP -. future .-> BL["BAM_BLACKLIST"]
    BL -. future .-> PC["PEAK_CALLER"]
    PC -. future .-> CONS["Replicate/consensus provider"]

    LEG["Legacy fallback"] --> FULL["peaks/full until native policies are validated"]
```

## Boundaries

- `CHIPSEQ_CONTEXT` is a compatibility adapter: it sources the existing project
  config and writes a content-tracked settings snapshot.
- `CHIPSEQ_METADATA` is provider-neutral validation and planning. It resolves
  FASTQs, models controls and distinguishes biological from technical identity.
- Existing `FASTQC` and `MULTIQC` modules are reused unchanged.
- Generic `REFERENCE_INDEX` and `ALIGNMENT` dispatch by `meta.aligner`; Bowtie2
  joins STAR as a provider without creating a ChIP-specific alignment API.
- Large data remain Nextflow outputs. Lightweight reports and provenance are
  published under `pipeline_info` and optional legacy-compatible target paths.

The Nextflow executor owns all scheduling. Modules contain no Slurm submission,
partition, account or host-specific path logic. Profiles select local, Slurm,
Docker, Conda, Singularity or Apptainer execution.

## Incremental migration order

1. metadata + raw QC + Bowtie2 alignment (this foundation);
2. separate BAM selection/index/QC contracts and measured duplicate policy;
3. explicit MACS3 provider and peak QC/FRiP;
4. reproducibility/consensus provider;
5. annotation, tracks and reporting;
6. differential binding only after a separate statistical design review.

