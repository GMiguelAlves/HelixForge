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

The scripts do not install software or remove data. Cluster paths, the Conda
executable, environment, and Slurm partition are explicit arguments.
