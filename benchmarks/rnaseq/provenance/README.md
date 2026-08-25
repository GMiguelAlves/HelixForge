# Provenance bundle contract

Each benchmark case must archive a small immutable audit bundle containing:

- RC tag, commit SHA and clean/dirty repository state;
- protocol/config/reference/input SHA-256 checksums;
- Nextflow, Java, container and package versions;
- exact commands and resolved parameters;
- Nextflow timeline, report, trace, DAG and `.nextflow.log`;
- Slurm job IDs and `sacct` resource export;
- task manifests and software version artifacts;
- metric tables, interpretation classes and final report;
- a short Portuguese `README.md` explaining the archive.

The archive name is
`rnaseq_<case>_<rc-tag>_<short-sha>_<UTC-timestamp>.tar.gz`. It is written to a
dedicated audit directory in the user's home only after checksum verification.
Raw FASTQs, indexes, Nextflow work directories and full result payloads remain on
scratch and are removed only after the audit archive has been verified.
