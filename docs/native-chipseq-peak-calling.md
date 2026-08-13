# Native ChIP-seq peak calling

## Architecture

```mermaid
flowchart TD
    META["Validated ChIP-seq metadata"] --> CTX["PEAK_CALLING_CONTEXT"]
    FINAL["FINAL_BAM + BAI + BAM manifest"] --> PAIR["Explicit treatment/control join"]
    CTX --> PAIR
    PAIR --> DISPATCH["PEAK_CALLING provider dispatch"]
    DISPATCH --> MACS["MACS3_CALLPEAK 3.0.4"]
    MACS --> AGG["PEAK_CALLING_AGGREGATE"]
    AGG --> OUT["Semantic peaks + metrics + provenance + manifest"]
```

Every IP record produces its own peak set. Controls are never peak-called and biological replicates are not pooled. Consensus and IDR remain future consumers of these independent manifests.

## Scientific decisions

| Question | Native decision | Reason |
|---|---|---|
| Narrow or broad? | Required explicitly | Target names are not reliable scientific classifiers. |
| Effective genome size? | Required as a positive numeric value | Avoid organism-specific aliases and the legacy sum-of-contigs approximation. |
| Paired-end input? | `BAMPE` | MACS3 then models observed fragments rather than only first-mate tags. |
| Duplicate handling? | Default `--keep-dup all` | Duplicate policy is already explicit in `BAM_DUPLICATES`; MACS3 must not add a hidden second policy. |
| Control association? | Exact record ID, or a unique control sample ID | Multiple possible control records fail instead of being selected by order. |
| No-control experiments? | Allowed explicitly for MACS3 | The manifest records the absence; no synthetic control is created. |
| FRiP? | Deferred | A reproducible denominator and overlap policy must be specified first. |

## MACS3 provider

MACS3 is pinned to version 3.0.4. Conda uses `macs3=3.0.4`; Docker and Apptainer use the matching Bioconda Python 3.12 build `3.0.4--py312h71493bf_0`. Resources start conservatively at 2 CPUs, 8 GB and 4 hours and require production benchmarking.

The command is constructed as an argument vector by a small Python runner, never evaluated as an arbitrary shell command. Complete command, input checksums, control checksum, reference identifier/checksum, caller environment, parameters and timing are recorded.

## Legacy comparison

The legacy caller uses MACS2/MACS3 without a fixed version, derives genome size from chromosome lengths when configured as `auto`, infers broad marks from a regular expression, and leaves MACS duplicate behavior implicit. Native v1 deliberately rejects those implicit decisions. Both retain per-IP calling, optional matched input, BAM/BAMPE selection and q-value support.

`--chipseq_run_mode peaks` uses the native API when `--chipseq_native_peak_calling true`. When false, only the legacy `peaks` step is invoked. Native `full` requires the native caller; native and legacy callers are never run simultaneously for one mode.

## Validation status

Validated in this development environment:

- Nextflow lint and top-level `peaks` stub;
- two independent treatment replicates joined to one explicit control;
- unit tests for caller/type/genome-size/cutoff validation, ambiguous or incompatible controls, duplicate identities and collisions;
- narrowPeak and broadPeak structural/coordinate validation;
- missing treatment/control BAM failures;
- isolated provider/aggregate stub and resume wiring.

Not validated here because MACS3 or a container runtime was not installed:

- functional MACS3 execution and biological peak production;
- real q-value, peak-type, BAM and control cache invalidation;
- Docker, Apptainer, Conda and Slurm execution;
- performance/resource benchmark.

The deterministic paired-end fixture and scripts are ready under `tests/native_chipseq_peaks/`; `run_functional.sh` and `run_cache_tests.sh` exit 77 with the explicit missing-runtime reason instead of downloading software automatically.

## Out of scope

Consensus, IDR, differential binding, annotation, motifs, GREAT, advanced visualization and complete FRiP are not implemented.
