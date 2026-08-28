# Slurm and data-handling policy

All compute-heavy commands run as Slurm jobs on compute nodes. The head node is
limited to source synchronization, small metadata inspection, checksum
verification when inexpensive, and job submission/accounting.

## Execution controls

- Nextflow is the sole scheduler; scripts may not call `sbatch`.
- Normal maximum queued/running HelixForge tasks: 5. A temporary ceiling of 10
  is allowed only after confirming a compute node is completely free; reduce
  it immediately when shared capacity becomes constrained.
- Execute benchmark arms serially in their frozen order.
- Use Nextflow 25.10.7 with Java 21 and record both at run start.
- Store each run under a unique, resolved directory below
  `/scratch/Schisto-epigenetics/gustavo/`.
- Never delete or move unrelated pre-existing data.

## Evidence lifecycle

1. Validate registry metadata and record `METADATA_VALIDATED`.
2. Submit resumable downloads as bounded Slurm jobs and record
   `DOWNLOAD_SUBMITTED`; do not keep an interactive session waiting.
3. Validate byte size and source checksum before recording `DOWNLOAD_READY`.
4. Run from immutable source inputs into a run-specific work/output directory.
5. Collect compact logs, manifests, versions, metrics, Nextflow reports, Slurm
   accounting and selected final outputs.
6. Put the evidence in a named archive under the user's home. Every archive
   contains a short Portuguese `README.md` explaining its purpose, inputs,
   status and checksums.
7. Verify archive integrity before cleaning scratch.
8. Remove only intermediates explicitly classified as reproducible and no
   longer required for audit or failure diagnosis.

If a run fails, retain the smallest sufficient failure bundle before cleanup.
Do not retain large work directories indefinitely merely because a job failed.
