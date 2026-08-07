# Minimal dry-run example

This tiny dataset is only for validation and `--dry-run` demonstrations. It is
not biologically meaningful.

Run:

```bash
bash chipseq_pipeline.sh --config config/example_pipeline_config.sh --all --dry-run
```

The example uses `PIPELINE_COMPRESS_RESULTS=1`, so large TSV-like outputs would
be named `.tsv.gz` in a real run.
