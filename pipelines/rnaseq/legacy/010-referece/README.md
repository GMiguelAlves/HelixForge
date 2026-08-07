# 010-reference

Prepare reference files and indexes. This step is organism-specific only through
`config/pipeline_config.sh`.

## Before You Run

Edit `config/user_settings.sh` and provide either URLs:

```bash
export GENOME_URL="https://..."
export TRANSCRIPTS_URL="https://..."
export GFF3_URL="https://..."
```

or local files:

```bash
export REF_GENOME_FA="/path/to/genome.fa"
export REF_TRANSCRIPTS_FA="/path/to/transcripts.fa"
export REF_GFF3="/path/to/annotations.gff3"
export REF_GTF="/path/to/annotations.gtf"
```

For Salmon, `REF_TRANSCRIPTS_FA` or `TRANSCRIPTS_URL` is required.
For STAR, `REF_GENOME_FA` or `GENOME_URL` is required.
For STAR with annotation, provide `REF_GTF`/`GTF_URL` or `REF_GFF3`/`GFF3_URL`.

If `QUANT_METHOD=star`, the pipeline uses the annotated STAR index
`STAR_INDEX_GTF_DIR` by default. This is the index needed for STAR
`--quantMode GeneCounts`.

## Run

Normally `rnaseq_pipeline.sh` submits this step. To run manually from the
repository root:

```bash
sbatch --chdir=010-reference scripts/010-reference/salmon_index.sh
sbatch --chdir=010-reference scripts/010-reference/star_index.sh
sbatch --chdir=010-reference scripts/010-reference/star_index_gtf.sh
```

Without Slurm, run the same scripts with `bash`:

```bash
bash scripts/010-reference/salmon_index.sh
bash scripts/010-reference/star_index.sh
bash scripts/010-reference/star_index_gtf.sh
```

Use `QUANT_METHOD`, `RUN_SALMON_INDEX`, `RUN_STAR_INDEX`, and
`RUN_STAR_GTF_INDEX` in `config/user_settings.sh` to choose which indexes the
pipeline should submit. The template sets the Salmon/STAR+GTF index defaults
from `QUANT_METHOD`.

## Outputs

- `010-reference/data/`
- `010-reference/salmon_index/`
- `010-reference/star_index/`
- `010-reference/star_index_gtf/`
- `010-reference/logs/`
