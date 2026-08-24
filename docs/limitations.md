# Current limitations

This page lists limitations that can affect current users. Historical
implementation and validation details are preserved separately in the
[validation records](index.md#historical-and-validation-records).

## Platforms and runtimes

- Linux x86_64 and WSL2 are supported. Native Windows execution is not.
- Nextflow 25.10.7 with Java 21 is the certified runtime baseline.
- Docker is the recommended local container runtime. Apptainer/Singularity and
  Conda profiles are experimental because a complete site-level certification
  was not available on the tested Slurm infrastructure.
- STAR is an experimental RNA-seq Alignment provider. Salmon is the supported
  production quantification path.

## Cache and shared filesystems

Nextflow `-resume` depends on both its task database and the unchanged work
directory. On one shared/WSL filesystem combination, complete runs succeeded
but the LevelDB task store persisted without task entries, causing eligible
tasks to run again. This is an operational limitation of that environment, not
a known change in scientific results. Confirm cache reuse on the target site
before relying on selective invalidation.

Compatibility outputs may retain configured absolute scratch paths. Docker
runs must bind those paths consistently, while shared HPC filesystems must be
visible to the selected container runtime. Manually deleting work-directory
outputs invalidates the corresponding cache entries.

## Scientific scope

- Synthetic and reduced fixtures validate contracts, determinism and provider
  execution. Large-scale technical and reviewed biological benchmarking is
  part of the v1 validation cycle and no superiority claim is made.
- RNA-seq batch variables are modeled through an estimable DESeq2 formula.
  Corrected matrices are exploratory only; the planned Batch Effect Assessment
  API is not part of the current workflow.
- Pathway enrichment providers such as GO, KEGG and Reactome are planned but
  are not yet part of the RNA-seq Report API.
- ChIP-seq technical sequencing records are aligned independently. A general
  biological-library BAM merge policy is not yet available, so input metadata
  must match the supported record/replicate model.
- STAR gene counts do not provide transcript effective lengths. The Import API
  marks length-dependent products unavailable instead of inventing values.

## Interoperability

Complete HelixForge runs emit portable terminal manifests and
`integration_artifacts/` bundles. Independently authored manifests must satisfy
the same schemas, semantic identity rules, checksums and mount-visible paths;
format-specific external adapters remain experimental.

Historical RNA-seq, ChIP-seq and Integrative implementations are available
only from their immutable retirement tags. They are audit and regression
references, not fallbacks in current workflows.
