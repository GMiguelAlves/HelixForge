# Workflow guide

HelixForge exposes four stable top-level workflow names through `--workflow`.
This guide describes their public intent and boundaries. The JSON parameter
schema remains the authoritative type/default reference.

## RNA-seq

**Purpose:** transform validated local FASTQs into quantified expression,
provider-neutral gene matrices, differential-expression results and optional
gene reports.

**Primary inputs:**

- `--rnaseq_config`: existing `pipeline_config.sh` describing local samples,
  metadata, transcriptome/genome annotation and reference inputs;
- `--rnaseq_de_spec`: versioned DE design/contrast JSON for `de`, `report`, or
  `full` modes;
- `--rnaseq_report_genes`: candidate-gene group file when the report is enabled.

**Modes:** `qc`, `alignment`, `quantification`, `import`, `de`, `report`, and
`full`. `quant` and `differential_expression` are accepted aliases. Salmon is
the production quantifier. STAR is an explicit experimental provider and is
independent from Salmon.

```bash
nextflow run . -profile docker \
  --workflow rnaseq \
  --rnaseq_run_mode full \
  --rnaseq_config configs/rnaseq/pipeline_config.sh \
  --rnaseq_de_spec configs/rnaseq/de_spec.json \
  --rnaseq_report_enabled true \
  --rnaseq_report_genes configs/rnaseq/report_genes.tsv \
  --outdir results
```

The DE design must be estimable. Batch is represented in the model, for example
`~ batch + condition`; corrected matrices are not substituted into inference.
The terminal contract is `results/rnaseq/rnaseq_run_manifest.json`.

## ChIP-seq

**Purpose:** transform validated local treatment/control FASTQs through QC,
alignment, BAM processing, peak calling, peak quality/replicate analysis,
differential binding, annotation, tracks and reporting.

**Primary inputs:**

- `--chipseq_config`: sample metadata, control relationships and references;
- explicit peak parameters including `--chipseq_peak_type` and
  `--chipseq_effective_genome_size`;
- `--chipseq_db_spec`: versioned design/contrast JSON for differential binding;
- an explicit consensus strategy or optional IDR parameters when applicable.

**Modes:** `qc`, `alignment`, `post_alignment`, `peaks`, `peak_qc`, `consensus`,
`idr`, `differential_binding`, `annotation`, `tracks`, `report`, and `full`.
Standalone annotation, tracks and report modes consume declared inventories and
do not rerun upstream stages.

```bash
nextflow run . -profile docker \
  --workflow chipseq \
  --chipseq_run_mode full \
  --chipseq_config configs/chipseq/pipeline_config.sh \
  --chipseq_peak_caller macs3 \
  --chipseq_peak_type narrow \
  --chipseq_effective_genome_size 123456789 \
  --chipseq_consensus_method replicate_support \
  --chipseq_min_replicates 2 \
  --chipseq_db_spec configs/chipseq/differential_binding.json \
  --outdir results
```

Values above are placeholders, not recommended biological defaults. Select
them for the organism, assay and design. IDR requires exactly two compatible,
premerged biological narrowPeak replicates plus explicit threshold and rank
metric. The terminal contract is
`results/chipseq/chipseq_run_manifest.json`.

## Integrative

**Purpose:** combine already-completed RNA-seq and ChIP-seq semantic evidence,
harmonize identifiers, link regulatory evidence, rank candidates, perform
functional interpretation and build a self-contained report.

**Required inputs:**

- `--rna_manifest` and its sibling `integration_artifacts/` directory;
- `--chip_manifest` and its sibling `integration_artifacts/` directory;
- versioned harmonization, interpretation, mark-role, prioritization-context,
  and functional-annotation policy files (normally supplied by the selected
  configuration/profile).

```bash
nextflow run . -profile local \
  --workflow integrative \
  --rna_manifest results/rnaseq/rnaseq_run_manifest.json \
  --chip_manifest results/chipseq/chipseq_run_manifest.json \
  --integrative_harmonization_policy configs/integrative/harmonization.json \
  --integrative_interpretation_policy configs/integrative/interpretation.json \
  --integrative_mark_roles configs/integrative/mark_roles.json \
  --integrative_prioritization_context configs/integrative/context.json \
  --integrative_functional_annotation configs/integrative/functional.tsv \
  --outdir results
```

The workflow rejects incompatible genomes/builds and invalid terminal
contracts before integration. The terminal contract is
`results/integration/integrative_run_manifest.json`.

## All

**Purpose:** coordinate the complete platform without adding an artificial
dependency between RNA-seq and ChIP-seq. Both assay DAGs run independently;
Integrative starts only from their terminal bundles.

```bash
nextflow run . -profile docker \
  --workflow all \
  --rnaseq_config configs/rnaseq/pipeline_config.sh \
  --rnaseq_de_spec configs/rnaseq/de_spec.json \
  --chipseq_config configs/chipseq/pipeline_config.sh \
  --chipseq_db_spec configs/chipseq/differential_binding.json \
  --outdir results
```

All workflow-specific required parameters still apply. `all` is convenience
orchestration, not a separate scientific model.

## Resources and profiles

Processes declare labels, CPUs, memory and time; profile/site configuration may
map these to infrastructure. Nextflow alone schedules tasks. No native module
submits nested jobs. See [Installation](installation.md) for supported profiles
and [Outputs](outputs.md) for the stable result boundary.
