# Risks and limitations

## Pre-execution blockers

- The institutional Slurm nodes previously exposed no supported Docker,
  Apptainer/Singularity or equivalent runtime. Because every scientific test
  must run on Slurm, Stage 9B may end as `BLOCKED_RUNTIME` unless a supported
  site runtime can execute the RC's pinned artifacts. The protocol forbids
  silently substituting a mixed host/Conda result for the certified RC run.
- GENCODE v49 creates a large Salmon index and raises the cost of an otherwise
  small benchmark. It is retained to avoid a toy reference and to keep human
  annotation current and explicit.
- Registry URLs, remote availability and upstream checksums can change.
  Downloads fail closed and the original registry plus computed digests remain
  in provenance.

## Scientific limitations

- Polyester's constant Q40 conversion does not model empirical FASTQ quality,
  adapter contamination, GC/PCR bias or complex sample preparation. Synthetic
  QC/trimming results are not biological ground truth.
- The synthetic model has no batch covariate and applies the same fold change
  to all isoforms of a DE gene. It tests the official first-release DE path,
  not isoform switching, batch-effect assessment or complicated confounding.
- The public dataset is small (four paired donors). Its publication used hg19,
  fixed cropping and Cufflinks/Cuffdiff, so DEG count and set agreement are
  contextual rather than exact validation.
- The 5 M-pair cap controls cost but is not the full archived experiment.
  Robustness conclusions apply to the declared cap and depth series only.
- One simulator and one public study cannot establish universal sensitivity,
  FDR control or biological performance across organisms and protocols.
- STAR remains experimental and is outside this benchmark. Results validate
  the Salmon production path only.

## Interpretation controls

- Thresholds marked `SANITY_CHECK` are investigation triggers, not advertised
  performance guarantees.
- Independent same-method agreement detects orchestration/contract drift but
  cannot reveal scientific limitations shared by Salmon, tximport and DESeq2.
- Queue wait and NFS contention are measured separately; neither is attributed
  to the scientific workflow implementation.
- Schistosoma biological validation and comparative production benchmarks are
  intentionally deferred until after this generic RNA-seq benchmark.
