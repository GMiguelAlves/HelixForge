# Native ChIP-seq architecture

The native foundation is deliberately smaller than the legacy workflow. It
implements explicit filtering contracts, stable final-BAM semantics and a
provider-neutral Peak Calling API.

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

    BAM --> SEL["BAM_SELECT"]
    SEL --> DUP["BAM_DUPLICATES"]
    DUP --> BL["BAM_BLACKLIST"]
    BL --> FINAL["BAM_INDEX_QC + FINAL_BAM"]
    PLAN --> PCTX["PEAK_CALLING_CONTEXT"]
    FINAL --> PC["PEAK_CALLING / MACS3"]
    PCTX --> PC
    PC --> PAGG["PEAK_CALLING_AGGREGATE"]
    PAGG --> PQC["PEAK_QC_CONTEXT"]
    FINAL --> PQC
    PQC --> FRIP["FRIP"]
    PQC --> PSTAT["PEAK_STATISTICS"]
    FRIP --> QAGG["PEAK_QC_AGGREGATE"]
    PSTAT --> QAGG
    QAGG -. future .-> CONS["Replicate/consensus provider"]

    LEG["Legacy fallback"] --> FULL["full or native peak calling disabled"]
```

## Boundaries

- `CHIPSEQ_CONTEXT` is a compatibility adapter: it sources the existing project
  config and writes a content-tracked settings snapshot.
- `CHIPSEQ_METADATA` is provider-neutral validation and planning. It resolves
  FASTQs, models controls and distinguishes biological from technical identity.
- Existing `FASTQC` and `MULTIQC` modules are reused unchanged.
- Generic `REFERENCE_INDEX` and `ALIGNMENT` dispatch by `meta.aligner`; Bowtie2
  joins STAR as a provider without creating a ChIP-specific alignment API.
- `CHIPSEQ_BAM_PROCESSING` owns independent selection, duplicate, blacklist and
  final integrity/index boundaries. Policies are values/files, never aligner
  side effects.
- `PEAK_CALLING_CONTEXT` resolves one treatment/control request per replicate;
  `PEAK_CALLING` dispatches MACS3 and aggregation publishes caller-neutral roles.
- `PEAK_QC_CONTEXT` safely joins final BAM and peaks by stable identity. `FRIP`
  and `PEAK_STATISTICS` remain independent cache boundaries and the final
  aggregator preserves one row per replicate.
- Large data remain Nextflow outputs. Lightweight reports and provenance are
  published under `pipeline_info` and optional legacy-compatible target paths.

The Nextflow executor owns all scheduling. Modules contain no Slurm submission,
partition, account or host-specific path logic. Profiles select local, Slurm,
Docker, Conda, Singularity or Apptainer execution.

## Incremental migration order

1. metadata + raw QC + Bowtie2 alignment (foundation 0.1);
2. BAM selection, duplicate policy, blacklist and final QC (foundation 0.2);
3. explicit MACS3 provider and caller-neutral peak outputs (foundation 0.3);
4. explicit FRiP/Peak QC API and per-replicate aggregation (foundation 0.4);
5. reproducibility/consensus provider;
6. annotation, tracks and reporting;
7. differential binding only after a separate statistical design review.
