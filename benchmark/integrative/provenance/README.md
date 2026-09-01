# Provenance contract

`scientific_target.json` freezes the exact code and upstream baseline lineage.
Future execution must add input manifests, reference checksums, policy
checksums, container digests, Nextflow/Java versions, Slurm job IDs and compact
trace summaries. Large work products remain outside Git and are represented by
checksums plus a Portuguese README in each retained audit archive.

No execution provenance exists yet because scientific execution has not
started.
