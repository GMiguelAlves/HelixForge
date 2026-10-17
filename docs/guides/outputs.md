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
- ChIP-seq: peaks, QC, annotations, BigWig tracks and the self-contained ChIP
  report; differential-binding tables only when explicitly requested.
- Integrative: `candidate_ranking.tsv`, functional interpretation tables, and
  `integration/100-report/integrative_report/integrative_report.html`.

Exact provider paths are recorded in manifests because some internal directory
names are intentionally not public API.

## Reproducibility classes

| Class | Examples | Comparison rule |
|---|---|---|
| Byte-exact integrity | A retained FASTQ, BAM/BAI or reference artifact | its declared cryptographic checksum must match the retained file |
| Semantic comparison across executions | BAM records, JSON manifests, TSV matrices, statistics | schema, identifiers, values and documented numerical tolerance; normalize only permitted headers, paths or timestamps |
| Generated presentation | HTML, plots, Nextflow reports | required sections/artifacts and scientific values; byte identity is not guaranteed |

Every native module emits version information and execution metadata according
to the [module contract](../api/module_contracts.md). Terminal manifests carry schema
and model versions independently from the HelixForge software version.

## Nextflow operational artifacts

Each top-level run enables:

- `<outdir>/pipeline_info/execution_trace.tsv`
- `<outdir>/pipeline_info/execution_timeline.html`
- `<outdir>/pipeline_info/execution_report.html`
- `<outdir>/pipeline_info/pipeline_dag.html`

These describe execution, not scientific meaning. Preserve them with the
terminal manifests when auditing a run. The `work/` directory and `.nextflow/`
cache are internal operational state and are not release artifacts.

The test profile and individual test configurations may disable presentation
reports or override these paths. On identical resume, scientific tasks with
unchanged inputs and retained outputs can be cached while a terminal manifest
is regenerated to record the new execution name. That provenance refresh is
not a repeated scientific analysis.
