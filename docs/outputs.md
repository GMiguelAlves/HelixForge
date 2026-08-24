# Outputs

## Stable boundary

The stable machine-readable output of each workflow is its terminal manifest:

```text
<outdir>/rnaseq/rnaseq_run_manifest.json
<outdir>/chipseq/chipseq_run_manifest.json
<outdir>/integration/integrative_run_manifest.json
```

RNA and ChIP manifests are accompanied by an `integration_artifacts/`
directory. Consumers resolve artifacts by semantic role in the manifest; they
must not search the results tree or infer meaning from filenames.

## Primary human outputs

- RNA-seq: differential-expression tables and the optional candidate-gene HTML
  report under the RNA results hierarchy.
- ChIP-seq: peaks, QC, differential-binding tables, annotations, BigWig tracks,
  and the self-contained ChIP report.
- Integrative: `candidate_ranking.tsv`, functional interpretation tables, and
  `integration/100-report/integrative_report/integrative_report.html`.

Exact provider paths are recorded in manifests because some internal directory
names are intentionally not public API.

## Reproducibility classes

| Class | Examples | Comparison rule |
|---|---|---|
| Byte-exact | FASTQ, BAM/BAI, fixed reference files | cryptographic checksum |
| Semantic | JSON manifests, TSV matrices, statistics | schema, identifiers, values and documented numerical tolerance; ignore permitted path/timestamp serialization |
| Generated presentation | HTML, plots, Nextflow reports | required sections/artifacts and scientific values; byte identity is not guaranteed |

Every native module emits version information and execution metadata according
to the [module contract](module_contracts.md). Terminal manifests carry schema
and model versions independently from the HelixForge software version.

## Nextflow operational artifacts

Each top-level run enables:

- `trace.txt`
- `timeline.html`
- `report.html`
- `dag.html`

These describe execution, not scientific meaning. Preserve them with the
terminal manifests when auditing a run. The `work/` directory and `.nextflow/`
cache are internal operational state and are not release artifacts.
