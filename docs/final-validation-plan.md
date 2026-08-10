# Final validation plan

This plan defines the work required before HelixForge can claim scientific
equivalence. The consolidation audit validates architecture and lightweight
contracts only; it does **not** constitute scientific validation.

## A. Mandatory before a scientific release

### Real-data equivalence

- Run legacy and native/hybrid RNA-seq on the same representative paired-end
  and, where supported, single-end datasets.
- Compare raw/trimmed/merged FASTQ checksums, FastQC metrics and MultiQC data.
- Compare STAR BAM/count outputs and Salmon `quant.sf`, command metadata,
  library-format counts and auxiliary files semantically.
- Compare Import API count, abundance and length matrices, sample tables,
  `tx2gene`, serialized experiments and metadata with documented numeric
  tolerances.
- Compare DESeq2 model coefficients, contrasts, adjusted p-values, fold changes
  and significant-gene sets against the legacy path.
- Run legacy and native/hybrid ChIP-seq on multiple references and layouts.
- Compare final BAM content/flags, duplicate and blacklist metrics, MACS3 peaks,
  FRiP, consensus intervals, differential binding, annotations and tracks.
- Confirm report component status and every embedded checksum against its source
  artifact.

### Cache and invalidation

- Demonstrate `-resume` reuse with no changes.
- Change one reference, annotation, FASTQ, scientific parameter and manifest at
  a time; verify that only the affected process and descendants rerun.
- Repeat on the target Slurm filesystem because metadata and symlink behavior
  can differ from local storage.

### Execution environments

- Build and publish the renamed `helixforge-*` OCI images.
- Record and verify image digests for Docker and Apptainer.
- Validate pinned Conda environments against the same tool versions.
- Execute reduced workflows on the production Slurm profile and verify CPU,
  memory, time, queue, retry and cancellation behavior.

### Integrative contract

- Define a versioned inventory that links RNA and ChIP outputs by explicit
  dataset, sample, genome/build and identifier namespace.
- Validate gene/transcript identifier compatibility and reference checksums
  before integration.
- Replace configured directory discovery with manifest inputs only after the
  legacy integrative baseline has been captured.

### Release evidence

- Archive inputs, references, configs, manifests, trace, timeline, report, DAG,
  software versions, container digests and Git commit.
- Publish a machine-readable comparison report and reviewer-approved deviation
  log. No unexplained scientific difference may be waived.

## B. Desirable before broad adoption

- Benchmark wall time, CPU efficiency, peak RSS, I/O and storage per API on at
  least two dataset sizes.
- Add property-based tests for manifest identities, joins and sample ordering.
- Add schema migration fixtures when a second manifest version is introduced.
- Test heterogeneous multi-reference projects and larger replicate structures.
- Add a small public validation bundle with redistribution-compatible data.
- Add automated provenance graph rendering from upstream manifest hashes.

## C. Non-blocking follow-up

- Implement a statistical IDR provider; current status remains
  `not_implemented` by design.
- Replace the ChIP-seq `full` legacy coordinator with native composition only
  after the staged native APIs pass section A.
- Migrate remaining reference/download/metadata and final-report wrappers.
- Replace historical compatibility environment variables after the immutable
  legacy RNA scripts are retired.
- Consider stricter domain-specific manifest schemas after real consumers and
  version-compatibility requirements exist.

## Acceptance rule

Architecture, stub and lint success are necessary but insufficient. A
scientific-release claim requires every item in section A, recorded evidence,
and explicit review of any tolerated numeric serialization difference.
