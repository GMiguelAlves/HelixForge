# 050-quantification

Import quantification files and generate gene-level matrices.

This step follows `QUANT_METHOD`:

- `salmon`: imports Salmon `quant.sf` with `tximport` and writes counts plus
  TPM.
- `star`: imports STAR `ReadsPerGene.out.tab` and writes counts plus CPM.

## Before You Run

Confirm these exist:

```text
${QUANT_DIR}/<PROJECT>/<sample_id>/quant.sf                  # Salmon mode
${STAR_QUANT_DIR}/<PROJECT>/<sample_id>/ReadsPerGene.out.tab # STAR mode
${REF_GTF}                                                   # Salmon mode
025-parse/030-metadata_final/AllProjects_metadata_new.csv
```

Relevant defaults in `config/pipeline_config.sh`:

- `METADATA_FINAL_NEW`
- `QUANT_METHOD`
- `QUANT_DIR`
- `STAR_QUANT_DIR`
- `STAR_GENECOUNT_COLUMN`
- `REF_GTF`
- `QUANTIFICATION_DIR`

## Run

Normally `rnaseq_pipeline.sh` submits this step. To run manually through Slurm:

```bash
bash scripts/050-quantification/run_quantification_slurm.sh --all
```

Force a method manually, if needed:

```bash
bash scripts/050-quantification/run_quantification_slurm.sh --all --method salmon
bash scripts/050-quantification/run_quantification_slurm.sh --all --method star
```

Without Slurm:

```bash
bash scripts/050-quantification/run_quantification_slurm.sh --all --local
```

Run one project:

```bash
bash scripts/050-quantification/run_quantification_slurm.sh PRJXXXX
```

Preview only:

```bash
bash scripts/050-quantification/run_quantification_slurm.sh --all --sbatch-dry-run
bash scripts/050-quantification/run_quantification_slurm.sh --all --local --sbatch-dry-run
```

## Outputs

- `050-quantification/counts_matrix.tsv`
- `050-quantification/tpm_matrix.tsv` when `QUANT_METHOD=salmon`
- `050-quantification/star_cpm_matrix.tsv` when `QUANT_METHOD=star`
- `050-quantification/quant_samples.tsv`
- `050-quantification/tx2gene.tsv` when `QUANT_METHOD=salmon`
- project-specific files when a single project is imported

`quant_samples.tsv` includes `quant_method`, `expression_unit`, and, for STAR,
the selected `star_count_column`.
