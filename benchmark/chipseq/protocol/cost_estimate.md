# Preliminary cost and storage estimate

These are planning bounds, not benchmark results. They prevent uncontrolled
use of the shared Slurm cluster and must be replaced by measured accounting in
the final reports.

## Input and reference storage

| Item | Download / generated size | Temporary working allowance |
|---|---:|---:|
| Synthetic reference and truth | <1 GiB | 5 GiB including indexes |
| Synthetic narrow FASTQs | approximately 8–12 GiB compressed | 60 GiB |
| Synthetic broad FASTQs | approximately 12–18 GiB compressed | 90 GiB |
| Real narrow FASTQs | 2.22 GiB | 80 GiB |
| Real broad FASTQs | 2.46 GiB | 100 GiB |
| Shared GRCh38 bundle and Bowtie2 index | approximately 5–8 GiB | 20 GiB |

The real arms share the 0.78 GiB compressed Input and reference bundle. Do not
duplicate them per arm. A conservative simultaneous scratch ceiling is 300
GiB; normal execution should remain below it by running arms serially and
cleaning eligible work only after evidence has been archived.

## Per-arm planning envelope

The ranges include HelixForge plus the independent implementation, but exclude
queue wait. CPU values are requested cores per largest task, not aggregate
core-hours.

| Arm | Libraries | Planned tasks | CPU per task | Peak RAM per task | Scratch allowance |
|---|---:|---:|---:|---:|---:|
| Synthetic narrow | 2 IP + 1 Input, 8 M PE pairs each | 30–50 | 2–8 | 4–24 GiB | 60 GiB |
| Synthetic broad | 2 IP + 1 Input, 12 M PE pairs each | 30–50 | 2–8 | 4–24 GiB | 90 GiB |
| Real narrow | 2 IP + 1 shared Input, 63.7 M SE reads total | 25–45 | 2–8 | 4–24 GiB | 80 GiB |
| Real broad | 2 IP + 1 shared Input, 69.7 M SE reads total | 25–45 | 2–8 | 4–24 GiB | 100 GiB |

## Per-process compute envelope

| Operation | Per-task planning request | Expected concurrency |
|---|---|---:|
| Synthetic generation | 4 CPU, 16 GiB, 8 h | 1 |
| FastQC | 2 CPU, 4 GiB, 2 h | up to 6 |
| Bowtie2 alignment | 8 CPU, 24 GiB, 12 h | up to 4 |
| BAM filtering/indexing | 4 CPU, 16 GiB, 6 h | up to 4 |
| MACS3 / FRiP | 4 CPU, 16 GiB, 4 h | up to 4 |
| IDR / consensus / evaluation | 2–4 CPU, 8–16 GiB, 4 h | up to 4 |

Normal concurrency is at most 5 jobs. A temporary ceiling of 10 is permitted
only after confirming that at least one compute node is completely free and
must be reduced when the shared queue becomes busy. Requests are ceilings, not
evidence of actual consumption. Slurm `sacct` and Nextflow trace data supply
measured time, CPU and peak memory.

## Network and archive policy

- Download once, verify checksums, and reuse read-only source files.
- Transfer in a small number of conventional SSH/SFTP operations; no parallel
  connection storm.
- Place processing data only below the user's designated scratch directory.
- Archive compact manifests, logs, checksums, metrics, reports and essential
  final scientific outputs in a named directory under the user's home.
- Do not archive work directories, duplicate reference indexes or intermediate
  BAMs unless required to explain a failure.
- Delete only run-specific, resolved scratch paths after archive verification.

## Stop conditions

Pause new submissions when the cluster queue is congested, the projected
scratch ceiling would be exceeded, a download checksum fails, or a task begins
an unexpected dependency cascade. A blocked runtime is reported rather than
worked around by installing a large unreviewed environment.
