# Configuration

This ChIP-seq pipeline follows the same configuration pattern as the RNA-seq
pipeline.

Most users should edit only:

```text
config/user_settings.sh
config/metadata.tsv
```

Create them with:

```bash
cp pipelines/chipseq/config/user_settings_template.sh pipelines/chipseq/config/user_settings.sh
cp pipelines/chipseq/config/metadata_template.tsv pipelines/chipseq/config/metadata.tsv
```

`config/pipeline_config.sh` is the advanced configuration engine. It loads
`config/user_settings.sh` automatically and defines all derived paths and
defaults used by the scripts.

Useful settings in `config/user_settings.sh`:

- `OUTPUT_DIR`: light project outputs such as logs, copied configs, and reports
- `WORK_ROOT`: heavy outputs on scratch, including indexes, trimmed FASTQs,
  BAMs, peaks, tracks, and count matrices
- `PIPELINE_COMPRESS_RESULTS`: use `1` to write large TSV-like outputs as
  `.tsv.gz`; downstream steps read `.tsv` and `.tsv.gz`
- `DIFF_PEAK_SET_SCOPE`: use `mark_all` to run differential binding only on
  `MARK__all` consensus peak sets, stratified by `mark_or_factor`; use `all`
  only when condition-specific peak sets should also be tested
- `THREADS`, `MEMORY`, and `SLURM_TIME`: configuration-adapter resource defaults
  consumed by the native configuration adapter when a module has no explicit
  override

Gzipped reference files are supported:

```bash
export GENOME_FASTA="/path/to/genome.fa.gz"
export ANNOTATION_FILE="/path/to/annotation.gtf.gz"
```

The workflow resolves these paths through the native ChIP-seq context and
submits every scientific process through Nextflow.
