# Limitations of the compatibility skeleton

- Legacy-wrapper outputs remain external side effects. Native QC, STAR,
  Salmon, and Import API outputs are content-tracked Nextflow artifacts and
  compatibility copies are published at the existing paths.
- ChIP raw QC, Bowtie2 alignment, BAM selection, duplicate policy, blacklist
  exclusion, final BAM QC, per-replicate MACS3 peak calling, Peak QC and
  interval consensus fan out natively. IDR has a validated provider boundary
  only. Differential Binding has native architecture and stub validation;
  annotation and tracks still use compatibility wrappers.
- The generic compatibility process uses resource classes rather than exact
  per-tool requirements.
- Container and native Conda profiles remain placeholders for legacy tools.
  Native RNA QC, STAR, Salmon, Import, ChIP metadata and Bowtie2 modules have
  pinned Conda environments. The combined Bowtie2/Samtools OCI execution path
  still requires a real container validation; stub validation does not prove
  that runtime composition.
- RNA-seq Report API orchestration and the clean
  `ghcr.io/gmiguelalves/helixforge-rnaseq-report:1.0.0` image are certified on a
  reduced real R execution. The module-owned `gene_set_report.R` is
  byte-identical to the reviewed legacy implementation. A broad biological
  benchmark remains a release gate; the duplicate legacy copy remains only for
  backward execution compatibility until legacy retirement.
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
  behavior. STAR and Salmon have separate real-tool Docker regressions; a real-tool QC
  golden dataset still needs to run on Linux/HPC with FastQC 0.12.1, Trim
  Galore 0.6.10, and MultiQC 1.17 available.
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
- MACS3 3.0.4 was not installed locally and no working container runtime was
  available during foundation 0.3 validation. Functional and cache scripts are
  present, but only unit/stub validation is claimed here. Peak QC and Consensus
  architecture, pure functions, schema and DAG were validated in stub mode; no
  real SAMtools/BEDTools FRiP or consensus value and no IDR result is claimed. The pinned
  Conda environment is defined, while a joint OCI image remains unpublished and
  therefore defaults to null rather than an unverified image reference.
- Native consensus uses a pinned Conda BEDTools version, but no verified joint
  OCI/Apptainer image is published yet. Its provider was not benchmarked or
  compared with the legacy union in this local stage. IDR is intentionally
  `not_implemented`: the manifest records unavailable peaks and no placeholder
  interval file is emitted.
- Differential Binding has not run real featureCounts or DESeq2 in this stage.
  The Subread and DESeq2 Conda environments are pinned, but featureCounts OCI/
  Apptainer parameters intentionally remain null until final validation. No real
  normalization, Wald statistic, p-value, legacy regression, biological
  comparison or benchmark is claimed.
- The v1 comparison universe is an explicit union of compatible condition-level
  Consensus BEDs. This is not IDR and may not be optimal for every experiment;
  final validation must compare it with curated and IDR-derived universes.
- Existing `.done` files remain active inside legacy pipelines. Nextflow status
  markers are an additional orchestration layer.
