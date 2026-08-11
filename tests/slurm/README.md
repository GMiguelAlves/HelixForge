# Controlled Slurm validation

These harnesses are intentionally small and conservative. They target an
isolated validation directory, submit at most one task at a time, and refuse
unexpected scratch paths.

- `run_trim_stub.sh` verifies Nextflow-to-Slurm submission without running the
  scientific command.
- `run_trim_real.sh` compares the legacy Trim Galore command with the native
  Nextflow process using the same reduced fixture and runtime environment.
- `run_salmon_real.sh` compares legacy Salmon index/quantification commands
  with the native Quantification API using the reduced transcriptome fixture.
- `run_star_real.sh` compares legacy STAR indexing/alignment commands with the
  native Alignment API using the reduced genome fixture.
- `run_import_salmon_real.sh` compares the legacy tximport script with the
  native Import API and validates the emitted `SummarizedExperiment`.
- `run_deseq2_real.sh` compares the legacy DESeq2 script with the native
  model/contrast/aggregation API using the golden reduced dataset.

The scripts do not install software or remove data. Cluster paths, the Conda
executable, environment, and Slurm partition are explicit arguments.
