# Current ChIP-seq implementation audit

## Audit boundary

The audit read `workflows/chipseq.nf`, the complete
`CHIPSEQ_NATIVE_FOUNDATION` composition, every ChIP-seq subworkflow, the
provider modules and the configuration/validation code at target commit
`0829c7c154dc634ffd4e13672b95ad4fbdc5957f`.

The official path actually implemented is:

```text
metadata/context validation
→ FastQC per declared FASTQ
→ MultiQC
→ Bowtie2 2.5.4 index and alignment
→ samtools 1.20 MAPQ/flag selection
→ duplicate policy (none/mark/remove)
→ optional fragment- or alignment-level blacklist removal
→ final BAM integrity/index/statistics
→ MACS3 3.0.4 per non-control replicate
→ FRiP + peak statistics
→ union/intersection/replicate-support consensus OR narrow IDR 2.0.4.2
→ optional featureCounts + DESeq2 differential binding
→ annotation + BigWig tracks + HTML/JSON report
→ terminal manifest in full mode
```

FastQC and alignment consume raw declared FASTQs. ChIP-seq trimming and
technical-replicate merging are not implemented. BWA is not an active provider.

## MACS3 invocation

The provider constructs an argument vector equivalent to:

```text
macs3 callpeak
  -t TREATMENT_BAM
  [-c CONTROL_BAM]
  -f BAM|BAMPE
  -g EFFECTIVE_GENOME_SIZE
  -n PEAK_ID
  --outdir OUTPUT_DIR
  --keep-dup all|auto|N
  -B
  -q CUTOFF | -p CUTOFF
  [--broad]
  [validated additional arguments]
```

The workflow requires an explicit positive effective genome size and an
explicit `narrow`/`broad` type. Paired libraries use `BAMPE`, so MACS3 uses
observed fragments; single-end libraries use `BAM` and MACS3's model. No
`--nomodel`, `--shift`, `--extsize`, `--call-summits` or `--broad-cutoff` is
added by HelixForge. In broad mode the MACS3 3.0.4 implicit broad cutoff is
therefore 0.1. The provider emits a semantic narrowPeak/broadPeak artifact,
the MACS3 output directory, command, logs, versions, timing and checksums.

## Protocol/implementation classifications

| Classification | Finding |
|---|---|
| `IMPLEMENTED_AND_BENCHMARKED` | QC, Bowtie2, BAM filtering, MACS3, FRiP and the selected replicate strategy are exercised in every applicable arm. |
| `IMPLEMENTED_NOT_BENCHMARKED` | Differential binding, peak-to-gene interpretation and the final `full` report are not correctness targets of the first peak benchmark. |
| `EXPERIMENTAL` | IgG can be represented as a control row, but its semantics are not distinguished from Input by validation. |
| `NOT_IMPLEMENTED` | ChIP-seq trimming, BWA, technical-replicate merge, cross-correlation and NRF/PBC library-complexity estimates. |
| `FUTURE_EXTENSION` | A two-condition differential-binding truth benchmark, motif discovery as a pipeline feature and additional organisms. |

## Recorded gaps; no fixes in this branch

- **IMPLEMENTATION_GAP:** `full` always composes differential binding and needs
  a valid contrast. Single-condition peak benchmarks must use `idr` or
  `consensus`; no fake condition is allowed.
- **IMPLEMENTATION_GAP:** non-`full` runs do not emit the top-level terminal run
  manifest, although their component manifests remain available.
- **IMPLEMENTATION_GAP:** broad cutoff 0.1 is inherited from MACS3 and is absent
  as a first-class field in the peak request. It remains reconstructable from
  the pinned version and command semantics.
- **DOCUMENTATION_GAP:** the historical peak-calling page still says FRiP was
  deferred in its migration-era table, while FRiP is now implemented. The page
  is explicitly marked historical; broad cleanup is deferred.
- **DOCUMENTATION_GAP:** some historical validation documents predate real
  complete Slurm execution, but their update sections record the later result.
- **POTENTIAL_BUG:** none identified that prevents the four planned core
  benchmarks. Broad mode itself has not yet received biological regression.
- **BENCHMARK_BLOCKER:** none for the frozen `idr`/`consensus` execution paths.

Differential binding remains official software functionality, but it is a
future benchmark requiring at least two biological conditions and its own
truth or reviewed contrast. It must not be inferred from ChIP versus Input.
