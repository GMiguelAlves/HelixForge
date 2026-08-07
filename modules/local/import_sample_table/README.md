# IMPORT_SAMPLE_TABLE

Joins authoritative metadata with validated import-source records. It preserves
the legacy first-row de-duplication and `dataset, sample_id` ordering while
adding two private columns used only to bind staged artifacts. Provider modules
remove private columns before publishing `quant_samples.tsv`.
