# Native ChIP-seq report

Report/Integration API v1 closes the functional native ChIP-seq DAG. It joins
already produced semantic manifests and explicitly declared result files; it
does not discover directories or run a scientific provider.

## Legacy audit

The legacy `report.sh` calls `render_report.R` with metadata and one output
root. The R script then discovers inputs through fixed directories, sample
filenames, and `list.files()` calls.

Scientific information extracted by the legacy report includes fastp read
counts/Q30, Bowtie2 mapping rates, aligned/final flagstat and samtools metrics,
peak type/count, replicate group counts, consensus region counts, annotation
classes, and differential significance summaries. Treatment/control affects
warnings and peak interpretation; replicates affect group summaries and power
warnings; consensus feeds count/differential summaries.

Presentation consists of HTML and Markdown, QC/group/differential TSVs, and
five PNG bar plots for alignment, peak counts, annotation classes, consensus,
and differential binding. Historical conventions include numbered directories,
sample-derived filenames, glob-first peak selection, `NA` for several missing
states, and a directory list standing in for tracks.

The native report preserves the useful scientific categories, not those
discovery conventions. It additionally exposes FRiP, explicit component
status, IDR `not_implemented`, tracks, reference identity, versions, parameters,
execution metadata, and provenance when supplied by native manifests. It does
not reproduce the legacy automatic warnings as scientific rules and does not
fabricate plots from incomplete inputs.

## Run

Copy `assets/chipseq_report_input.example.json`, replace every manifest and
artifact path, then run:

```bash
nextflow run . -profile local --workflow chipseq \
  --chipseq_run_mode report \
  --chipseq_native_report true \
  --chipseq_report_input_manifest /path/to/chipseq_report_input.json
```

The unchanged fallback is:

```bash
nextflow run . -profile local --workflow chipseq \
  --chipseq_run_mode report \
  --chipseq_native_report false
```

The renderer supports `--chipseq_report_provider html_v1`,
`--chipseq_report_title`, and `--chipseq_report_language en|pt-BR`.

## Outputs

`chipseq/report/report_result` contains:

- `chipseq_report.html`: self-contained HTML with embedded CSS;
- `report.json`: provider-neutral structured report;
- `manifest.json`: final semantic output contract;
- `provenance.json`;
- `versions.yml`;
- `execution.json`.

Context and intermediate aggregation records are published below
`pipeline_info/native_chipseq/report`. Missing optional components render as
`Not executed`; unavailable metrics remain null/`Not available`.

## Validation completed

- eight unit/semantic tests passed;
- required and optional components, ID association, build conflicts, checksum
  declarations, IDR status, HTML escaping, and schema/example roles were tested;
- isolated stub execution completed and all three tasks were cached by
  `-resume`;
- top-level native and fallback stub modes completed;
- Nextflow lint completed without errors or new warnings;
- no nested scheduler command exists in the native report graph;
- the legacy ChIP-seq directory was not modified.

No biological dataset, benchmark, Slurm, container runtime, scientific visual
review, or complete legacy comparison was run. The result is an executable
architecture, not a scientific-equivalence claim.

## Next activity

Do not add another major ChIP-seq feature. The next activity is consolidated
scientific review and real execution of the complete DAG: validate providers,
selective legacy regressions, resources, Slurm, containers, outputs, and only
then retire wrappers that are proven unnecessary.
