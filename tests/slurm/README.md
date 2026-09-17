# Controlled Slurm validation

These harnesses are intentionally small and conservative. They target an
isolated validation directory and refuse unexpected scratch paths. Individual
stage harnesses submit one task at a time; the top-level RNA production
validation permits at most five concurrent tasks.

- `run_trim_stub.sh` verifies Nextflow-to-Slurm submission without running the
  scientific command.
- `run_trim_real.sh` compares the legacy Trim Galore command with the native
  Nextflow process using the same reduced fixture and runtime environment.
- `run_salmon_real.sh` compares legacy Salmon index/quantification commands
  with the native Quantification API using the reduced transcriptome fixture.
- `run_star_real.sh` compares legacy STAR indexing/alignment commands with the
  native Alignment API using the reduced genome fixture.
- `run_bowtie2_real.sh` compares legacy Bowtie2 indexing/alignment with the
  native Alignment API using one sequential task at a time.
- `run_chipseq_bam_real.sh` validates native selection, duplicate handling,
  blacklist filtering, indexing, and QC on a reduced BAM fixture.
- `run_chipseq_peaks_real.sh` validates native MACS3 peak calling for two
  treatment replicates against one control.
- `run_chipseq_peak_qc_real.sh` connects those real BAM and peak artifacts to
  the native FRiP and peak-statistics API.
- `run_chipseq_consensus_real.sh` validates union consensus using the real peak
  and FRiP manifests from the preceding controlled cases.
- `run_chipseq_db_real.sh` validates featureCounts, a DESeq2 binding model, two
  contrasts, and the aggregate on a reduced four-replicate dataset.
- `run_chipseq_annotation_real.sh` validates coordinate-aware peak annotation,
  statistics, and aggregation on a reduced reference and GTF.
- `run_chipseq_tracks_real.sh` validates individual and aggregate BigWig tracks
  from the real reduced ChIP-seq BAM fixture.
- `run_chipseq_report_real.sh` validates report context, aggregation, and the
  self-contained HTML provider on a complete reduced component inventory.
- `run_import_salmon_real.sh` compares the legacy tximport script with the
  native Import API and validates the emitted `SummarizedExperiment`.
- `run_deseq2_real.sh` compares the legacy DESeq2 script with the native
  model/contrast/aggregation API using the golden reduced dataset.
- `run_rnaseq_production_real.sh` validates the official top-level
  QC -> Salmon -> Import -> DESeq2 -> Gene Report path, then attempts identical
  and selective invalidation scenarios. `baseline-driver` executes only the
  complete synthetic scientific baseline, while `resume-driver` continues a
  completed baseline without overwriting its evidence. `short-matrix-driver`
  verifies identical resume plus FASTQ, transcriptome, contrast and QC
  parameter invalidation without the longer module-mutation scenarios.
- `run_chipseq_production_real.sh` validates the complete supported ChIP-seq
  path using a deterministic paired-end fixture and at most five concurrent
  Slurm jobs. It chains `differential_binding`, `annotation`, `tracks`, and
  `report` through their published manifests; `recovery-driver` skips stages
  whose archived trace already exists.
- `generate_chipseq_production_fixture.py`,
  `prepare_chipseq_downstream.py`, and
  `validate_chipseq_production.py` generate the reduced dataset, construct
  manifest-backed inputs between top-level modes, and validate scientific and
  operational outputs. The validated 2026-08-13 case completed 100 scientific
  tasks with Nextflow 25.10.7.
- `cache_probe.nf` and `cache-probe.config` provide a one-process diagnostic
  for task-cache persistence independently of the scientific DAG.
- `cache_scale_probe.nf` and `cache-scale-probe.config` vary only the number of
  trivial task invocations, with at most five simultaneous Slurm jobs, so a
  site can distinguish a single-task success from a scale/filesystem cache
  failure without processing scientific data.
- `cache_tuple_probe.nf` isolates the tuple-input shape used by real HelixForge
  modules from the minimal scalar cache probe.
- `cache_standard_probe.nf` distinguishes the default cache mode from the
  suite's deep-content cache policy.

Before a production `-resume`, create a receipt immediately after the original
run and validate it against the live cache:

```bash
bin/helixforge-resume-guard capture \
  --run-name RUN_NAME \
  --receipt /persistent/audit/resume-receipt.json \
  --work-dir /shared/work

bin/helixforge-resume-guard check \
  --run-name RUN_NAME \
  --receipt /persistent/audit/resume-receipt.json \
  --work-dir /shared/work
```

The same `NXF_CACHE_DIR`, launch directory and Nextflow executable used by the
workflow must be present for both commands. A missing/empty task database,
changed task inventory, absent work directory, or non-zero `.exitcode` fails
closed before Nextflow can submit work. Only a successful check authorizes
`-resume RUN_NAME`; the guard does not reconstruct or replace Nextflow cache
entries.

An earlier version/JVM matrix appeared to identify runtime-dependent cache
behavior. That comparison is not accepted as evidence because its failing
harnesses invoked the Nextflow JAR directly while the successful control used
the official launcher. The apparent difference was caused by launch method,
not filesystem or Slurm. With the official Nextflow 25.10.7 launcher and Java
21, the complete RNA workflow persists task records and an identical resume
recovers all scientific tasks from cache. The short selective matrix also
passes FASTQ, transcriptome, contrast and trim-quality boundaries. The
corrected evidence and operational policy are maintained in
`docs/resume-cache-diagnostic.md`.

All harnesses must receive an official launcher through `NEXTFLOW_BIN` or
`HELIXFORGE_NEXTFLOW_BIN`. A wrapper that delegates to `java -jar` is not a
supported launcher.

The scripts do not install software or remove data. Cluster paths, the Conda
executable, environment, and Slurm partition are explicit arguments.
