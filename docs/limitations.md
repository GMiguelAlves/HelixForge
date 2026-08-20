# Limitations of the compatibility skeleton

- Legacy-wrapper outputs remain external side effects. Native QC, STAR,
  Salmon, and Import API outputs are content-tracked Nextflow artifacts and
  compatibility copies are published at the existing paths.
- ChIP raw QC, Bowtie2 alignment, BAM selection, duplicate policy, blacklist
  exclusion, final BAM QC, per-replicate MACS3 peak calling, Peak QC and
  interval consensus fan out natively. Optional IDR 2.0.4.2, Differential
  Binding, annotation, tracks and report are native and composed by `full`.
- The generic compatibility process uses resource classes rather than exact
  per-tool requirements.
- Native ChIP scientific runtimes are now pinned by OCI digest. Dedicated clean
  images cover Bowtie2/Samtools, FRiP/interval consensus, featureCounts and
  tracks; immutable upstream images cover MACS3, annotation and report. All
  seven passed reduced functional Docker certification in run `32368534261`.
  A complete top-level Docker execution and an Apptainer execution remain
  pending. Slurm probes `14748`/`14749` confirmed that the Debian 13 compute
  node exposes no supported container runtime; no user-managed installation
  was introduced. This is a documented site limitation, not a HelixForge
  release gate.
- RNA-seq Report API orchestration and the clean
  `ghcr.io/gmiguelalves/helixforge-rnaseq-report:1.0.0` image are certified on a
  reduced real R execution. The module-owned `gene_set_report.R` is
  text-identical after LF normalization to the reviewed legacy implementation.
  The complete synthetic production path also passed on Slurm. A broad
  biological benchmark remains a post-release validation milestone; the
  duplicate legacy copy is preserved by tag before retirement.
- Docker runs must bind the configured external `SCRATCH_ROOT` at the same path
  inside the container because compatibility outputs retain their absolute
  legacy paths. Shared HPC filesystems are normally visible to Apptainer.
- Cached native QC tasks track their work-directory outputs. If a user manually
  deletes compatibility copies under `SCRATCH_ROOT`, resume should be avoided
  or the affected task cache should be invalidated.
- Alignment and Quantification cache/invalidation previously passed in
  isolated tests with Nextflow 26.04.2, but 26.04.4/26.04.6 did not resume a
  minimal Slurm probe. HelixForge is temporarily pinned to Nextflow 25.10.7,
  which resumed the same probe on both Java 21 and Java 23 and completed the
  full RNA path. Its identical full-DAG resume nevertheless left the LevelDB
  task store empty and resubmitted jobs. Selective invalidation remains a
  release gate and was not inferred after that prerequisite failed.
- The deterministic QC mock validates orchestration and byte-preserving merge
  behavior. MultiQC 1.17 has a real reduced Docker certification with an OCI
  digest; STAR and Salmon have separate real-tool Docker regressions. A broad
  reviewed biological QC regression is still a release gate.
- STAR does not estimate transcript effective lengths, so Import API v1 marks
  length and `SummarizedExperiment` artifacts unavailable for that provider
  instead of inventing values.
- The unchanged legacy Salmon importer contains a scalar `ifelse` expression
  that recycles the first import ID for multi-sample metadata. Regression uses
  one sample to execute that script unchanged; the native two-sample fixture
  validates the intended unique-ID behavior used downstream.
- `workflow all` waits for RNA and ChIP before integration, but the existing
  IntegrateSeq config must point to the actual RNA/ChIP result directories.
- The minimal output manifest and Reference Bundle are specified but not yet
  generated automatically.
- Native ChIP-seq foundation 0.3 aligns technical sequencing records
  independently. It validates their identity but does not yet merge them into
  biological-library BAMs. MAPQ, duplicate and blacklist policies are native.
  Peak Calling API v1 preserves each execution record independently; a future
  library-level merge policy is still required before biological consensus.
- MACS3, FRiP, interval consensus, featureCounts and tracks now have functional
  Docker evidence and immutable defaults. The complete reduced top-level Slurm
  execution also passed with real tools, including optional IDR, Differential
  Binding, annotation, tracks and report. Because the cluster exposes no
  container runtime, a same-cluster Apptainer execution and the reviewed
  biological regression remain pending.
- The v1 comparison universe is the explicit union of compatible condition-level
  completed Consensus or IDR BEDs. Choosing IDR changes the per-condition peak
  evidence but does not silently change the cross-condition universe policy.
- Existing `.done` files remain active inside legacy pipelines. Nextflow status
  markers are an additional orchestration layer.
