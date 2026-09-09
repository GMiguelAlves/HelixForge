# CHIPSEQ_FULL_REPORT_INPUT

Builds the report inventory directly from manifests and semantic artifacts
emitted in the active `chipseq_run_mode=full` session. It never searches
published result directories. The staged manifests and semantic artifacts are
published beside the inventory so that every relative path remains resolvable
after the originating work directory is removed.
