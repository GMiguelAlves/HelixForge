# Nextflow resume-cache diagnostic

## Resolution

The HelixForge cache-persistence incident is resolved. The affected validation
harnesses invoked `nextflow-25.10.7-one.jar` directly with `java -jar` instead
of using the official Nextflow launcher. That bypassed JVM module-opening
options supplied by the launcher. Chill/Kryo serialization then raised a Java
module-access exception inside the asynchronous cache writer. The workflow
could finish successfully while its LevelDB database contained run indexes but
no task entries.

HelixForge now requires the official Nextflow launcher. Direct invocation of a
Nextflow JAR is unsupported in production and test harnesses.

The correction was verified on the shared Slurm environment with Nextflow
25.10.7 and Java 21:

- the minimal probe resumed with the original task hash and no new Slurm job;
- the complete synthetic RNA-seq workflow persisted 59 task records;
- an identical resume recovered all 58 scientific tasks as `CACHED`;
- only the terminal `RUN_MANIFEST` process executed again because its declared
  per-run provenance contains the dynamic Nextflow run identity;
- QC, Salmon, Import, DESeq2 and Gene Report outputs passed their scientific
  validators after resume.

This result excludes NFS, Slurm, Debian 13, workflow scale and the scientific
DAG as the root cause of the observed empty task databases. The selective
invalidation matrix maintained by
`tests/slurm/run_rnaseq_production_real.sh` also passed:

| Change | Observed invalidation boundary |
|---|---|
| None | All 58 scientific tasks were `CACHED`; terminal run manifest regenerated |
| One sample FASTQ | Only that sample's QC, quantification and dependent analyses reran |
| Transcriptome | Salmon index, all quantifications and dependent analyses reran; QC stayed cached |
| DESeq2 contrast | Import and model stayed cached; contrast, aggregation and reports reran |
| QC trim quality | Raw FastQC and Salmon index stayed cached; affected QC and descendants reran |

The short matrix deliberately keeps Salmon parameters constant while testing
contrast and QC changes, so each scenario measures one invalidation boundary.

## Historical investigation

The original investigation observed that one small probe could resume while a
complete workflow could not. A later diagnostic matrix reproduced an empty
task database on NFS and local ext4, with deep/default cache modes and different
task counts. Those observations were real, but their interpretation was
incomplete: all failing cases used a direct-JAR wrapper, whereas the successful
control used the official launcher.

The direct-JAR wrapper later installed in the user's local runtime did not
originate the problem. Earlier full-workflow harnesses already used the same
unsupported `java -jar` pattern. The wrapper merely made that historical
pattern the default for subsequent probes.

The investigation was reported upstream as
[nextflow-io/nextflow#7471](https://github.com/nextflow-io/nextflow/issues/7471).
The cache failure itself was caused by the HelixForge runtime harness. A useful
upstream diagnostic observation remains: the asynchronous writer retained the
serialization exception without failing the workflow, allowing a successful
run to leave an empty task database.

This was not the missing-history scenario described in
[Nextflow discussion #4876](https://github.com/nextflow-io/nextflow/discussions/4876).
The launch directory, session history, cache directory and work outputs were
all preserved. The missing component was the serialized task entry.

## Supported launcher contract

Use the official launcher and keep the certified version explicit:

```bash
export NXF_VER=25.10.7
nextflow -version
nextflow run . [arguments]
```

When the launcher is installed under a site-specific name, pass its executable
path through `NEXTFLOW_BIN` for local test harnesses or
`HELIXFORGE_NEXTFLOW_BIN` for controlled Slurm harnesses. The value must be an
official launcher executable, not a script that delegates to `java -jar`.

## Resume guard

`helixforge-resume-guard` remains available as defense in depth for expensive
production runs. It validates a private receipt against live task records and
preserved work outputs before a resume is attempted. It is no longer a
workaround for a known HelixForge cache defect.

The receipt contains relative work paths and belongs in the private execution
audit, not in the public repository. The guard fails closed when task records
or work outputs have been removed, which protects users from an accidental
full recomputation after manual cleanup.

## Operational policy

1. invoke Nextflow only through its official launcher;
2. preserve `.nextflow`, the configured cache directory and `work` outputs for
   as long as resume is required;
3. use the same launch directory and runtime version when resuming;
4. run the resume guard for costly production executions;
5. use manifest re-entry when the original task cache or work directory has
   intentionally been retired.
