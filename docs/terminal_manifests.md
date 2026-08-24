# Terminal assay manifests

## RNA-seq

`rnaseq_run_manifest.json` carries explicit samples, technical runs,
conditions, stages, batches, quantification method and DE contrasts. Terminal
artifact roles include available gene counts, transcript abundance, normalized
counts, DE tables and the optional gene report. Optional products are omitted;
they are not represented by invented files or zero-valued measurements.

## ChIP-seq

`chipseq_run_manifest.json` preserves each sequencing record, biological and
technical replicate, control association, condition, stage and mark/factor.
Peak sets declare narrow/broad type. Consensus or IDR peaks, peak-to-gene
associations and differential-binding results are scientific artifacts. BAMs,
signal tracks and the report remain useful terminal products but their role is
explicitly distinct from evidence integration.

## Generation

`RUN_MANIFEST` receives the normalized metadata, Reference Bundle manifest,
upstream manifests and an ordered set of semantic artifact descriptors directly
from the workflow. Paths are tracked Nextflow inputs. The process adds checksums
and provenance, validates the result and publishes it without changing any
scientific output directory or filename.

Normal executions validate the generated document against JSON Schema Draft
2020-12 and then apply semantic checks. Dependency-free `-stub-run` execution
still applies the semantic contract but records schema validation as
`skipped_stub`; the same fixture is validated against the real schema engine by
the Python contract suite and CI.

Complete assay DAGs emit the v1 terminal contract. Stage-specific modes expose
their domain manifests; an
external assembler may use the same schemas after declaring all required run
context.

## Integrative

`integrative_run_manifest.json` consumes exactly one RNA and one ChIP terminal
manifest. It records compatibility validation, every component-manifest
checksum, model/policy versions and run-relative checksums for the Master,
interpretation, functional, visualization and report products. It is produced
from typed channels and cannot be assembled by scanning output filenames.

Normal assay terminal manifests also publish a compact
`integration_artifacts/` bundle containing only products eligible for evidence
integration. This makes independent manifest re-entry portable without copying
large BAM, track or unrelated report artifacts.
