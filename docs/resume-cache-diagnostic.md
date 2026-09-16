# Nextflow resume-cache diagnostic

## Operational decision

Production `-resume` is fail-closed in HelixForge. A launcher may add
`-resume RUN_NAME` only after `bin/helixforge-resume-guard check` verifies a
receipt captured from the same run, live task-cache records and preserved work
directories. If the check fails, use a documented manifest re-entry boundary;
do not retry the complete workflow with an unverified cache.

This control prevents accidental recomputation. It does not reconstruct
LevelDB records and is not presented as a fix inside Nextflow.

## Controlled observations

The original August 2026 investigation used Debian 12, Nextflow 25.10.7 and
Java 21/23. Its one-task Slurm probe resumed correctly, while a complete RNA
workflow finished with an empty task database. Nextflow 26.04.x also missed the
one-task cache on NFS and local ext4. The behavior was reported upstream as
[nextflow-io/nextflow#7471](https://github.com/nextflow-io/nextflow/issues/7471).

The institutional cluster was subsequently upgraded to Debian 13. A focused
rerun on 16 September 2026 produced the following matrix:

| Nextflow | Java | Driver/cache filesystem | Probe | Task records |
|---|---|---|---|---:|
| 25.10.7 build 12755 | Temurin 21.0.12+8 | NFS/NFS | 16 trivial Slurm tasks | 0 |
| 25.10.7 build 12755 | Temurin 21.0.12+8 | NFS/local ext4 | 16 trivial Slurm tasks | 0 |
| 25.10.7 build 12755 | Temurin 21.0.12+8 | NFS/local ext4 | 2 serialized trivial tasks | 0 |
| 25.10.7 build 12755 | Temurin 21.0.12+8 | NFS/local ext4 | exact original one-task probe | 0 |
| 25.10.7 build 12755 | Temurin 21.0.12+8 | local ext4/default local cache | exact original one-task probe | 0 |
| 25.10.7 build 12755 | Temurin 21.0.12+8 | NFS/local ext4 | default rather than deep cache mode | 0 |

Every task completed with exit status zero and retained its work directory and
`.exitcode`. Every cache database opened and closed without a reported error,
wrote the history and run index, but retained an empty LevelDB log with no task
records. An actual `-resume` of the exact original probe submitted a new Slurm
task with a new work hash.

This is not the missing-history scenario described in
[Nextflow discussion #4876](https://github.com/nextflow-io/nextflow/discussions/4876).
In that cloud case, a new launch directory/container cannot discover the prior
session because `.nextflow/history` was not preserved; an explicit session and
`NXF_IGNORE_RESUME_HISTORY=true` can bypass history lookup. In this controlled
case, both invocations used the same launch directory and history, explicit
`-resume RUN_NAME` resolved the original UUID, and the corresponding LevelDB
still had no task values to recover. Ignoring history cannot restore absent
task records.

The Nextflow JAR and Java installation predate the cluster upgrade and remained
fixed during this matrix. The result rules out the scientific DAG, task count,
concurrency, `cache 'deep'`, NFS cache placement and `NXF_CACHE_DIR` as a
sufficient explanation. It identifies a site/runtime regression after the OS
upgrade, but does not establish which external component causes Nextflow to
discard task records silently.

## Guard contract

`helixforge-resume-guard capture` must run after the original Nextflow process
returns and before cache/work cleanup. It writes a private receipt containing:

- schema and explicit Nextflow run name;
- exact task count;
- task hash/name identities;
- work paths relative to the declared work root.

`helixforge-resume-guard check` reruns `nextflow log` in the same launch/cache
context and requires:

- at least one task record;
- at least one recoverable record (`COMPLETED` or `CACHED`, exit zero), while
  failed/aborted attempts are reported and excluded from the receipt;
- the exact captured task inventory;
- every task work directory below the declared root;
- `.exitcode=0` in every recorded work directory.

No absolute site path is written to the receipt. The receipt belongs in the
private execution audit, not in the public repository.

## Safe continuation policy

Until an upstream or site-runtime correction passes the probes:

1. do not use bare `-resume` in production launchers;
2. stop before submission when the guard fails;
3. preserve completed terminal manifests and published results;
4. restart from the narrowest supported re-entry mode rather than from raw
   FASTQs;
5. keep the upstream issue open and attach only sanitized diagnostics.

Selective cache invalidation remains uncertified. Scientific results already
validated from completed executions are unaffected by this operational defect.
