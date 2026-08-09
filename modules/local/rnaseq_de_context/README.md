# RNASEQ_DE_CONTEXT

Reads `config/pipeline_config.sh` only to stage the configured annotation and
stages the user-supplied `rnaseq_de_spec` unchanged. It never derives a design,
contrast, or filtering rule from legacy variables. This is a temporary
compatibility adapter, not a statistical module.
