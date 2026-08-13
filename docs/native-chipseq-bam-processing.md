# Native ChIP-seq BAM processing

BAM Processing API version: `0.1`

This layer converts a provider-neutral aligned BAM into a validated final BAM
without hiding scientific filters inside the aligner.

## Execution graph

```mermaid
flowchart LR
    A["ALIGNMENT: sorted BAM + BAI"] --> S["BAM_SELECT"]
    S --> D["BAM_DUPLICATES"]
    D --> B["BAM_BLACKLIST"]
    B --> Q["BAM_INDEX_QC"]
    Q --> F["FINAL_BAM + BAI + manifest"]
    F -. optional compatibility .-> P["Legacy peak calling"]
```

The aligned BAM is already coordinate-sorted. Selection is performed first to
reduce the data passed to duplicate detection. Duplicate handling is next
because it is an independent library policy. Blacklist exclusion follows so a
paired `fragment` policy can remove the complete template. The final index and
QC describe the artifact actually delivered to peak calling. `BAM_INDEX_QC`
can sort explicitly when requested, but the ChIP-seq workflow fails on an
unexpected sort order by default.

## BAM_SELECT

Input: `tuple(meta, BAM, BAI, reference FASTA, selection parameters)`.

Parameters are explicit and cache-tracked:

- `min_mapq`: integer 0–255;
- `include_flags`: SAM flag bitmask required with `samtools view -f`;
- `exclude_flags`: SAM flag bitmask rejected with `samtools view -F`;
- `region`: optional explicit SAMtools region.

Compatibility defaults come from the existing config: MAPQ 30, include mask 0,
and exclude mask 2308 when secondary/supplementary removal is enabled. Decimal
2308 is recorded rather than hidden: unmapped `4` + secondary `256` +
supplementary `2048`. Proper pairs are measured but not silently required; a
caller that wants this must explicitly set include flag `2`.

Before selection, the module checks BAM/BAI integrity, coordinate sort order,
and exact reference contig names and lengths. It never normalizes `chr1`/`1` or
`MT`/`chrM` automatically.

## BAM_DUPLICATES

`duplicate_mode` is mandatory and accepts:

- `none`: retain the BAM and report only pre-existing duplicate flags;
- `mark`: detect and retain duplicates with flag 1024;
- `remove`: detect, measure, then remove flag-1024 records.

The native default is `none`; duplicate removal is not assumed to be correct
for every ChIP experiment. `legacy` may be requested at workflow level to map
the old `REMOVE_DUPLICATES` setting, but only the SAMtools provider is currently
supported.

Paired BAMs use name sort → `fixmate -m` → coordinate sort → `markdup -s`.
Single-end BAMs use `markdup -s` directly on coordinate-sorted input. Native
removal marks first and filters second so duplicate counts are always available;
the legacy script uses `markdup -r` directly.

## BAM_BLACKLIST

The BED is optional. When absent, the module copies the input and records
`blacklist_enabled=false`. When present it validates:

- at least three BED columns;
- non-negative integer coordinates and `end > start`;
- every BED contig exists in the validated BAM/reference contig table.

No blacklist is supplied by organism name. Two explicit overlap policies are
available:

- `fragment` (native default): remove every alignment sharing a QNAME with an
  overlapping alignment, preserving paired-template consistency;
- `alignment`: exclude only overlapping alignment records, matching the legacy
  `bedtools intersect -v -abam` semantics more closely.

## BAM_INDEX_QC

This final boundary validates integrity and reference compatibility again,
verifies or explicitly restores coordinate order, creates the BAI and emits:

- `flagstat`, `idxstats`, `stats`;
- header and contig tables;
- reference compatibility diff;
- MAPQ distribution;
- total, mapped, properly paired and duplicate-flagged counts;
- command, versions, checksums, execution metadata and final manifest.

The compatibility artifact remains
`060-filtering/<record_id>/<record_id>.filtered.bam`.

## Workflow modes

```bash
nextflow run . --workflow chipseq --chipseq_run_mode post_alignment
```

This BAM-layer release introduced native `qc`, `alignment`, and
`post_alignment`; foundation 0.3 additionally provides native `peaks`. Native
`full` now consumes this layer directly. Setting
`--chipseq_native_foundation false` remains a compatibility choice only for
supported dedicated modes.

To use only legacy peak calling after native BAM processing:

```bash
nextflow run . --workflow chipseq --chipseq_run_mode post_alignment \
  --chipseq_continue_legacy_peaks true
```

This works through the exact final compatibility BAM paths; native code does
not parse caller-specific peak outputs in this stage.

## Reduced validation

The real local SAMtools 1.20 fixture contains paired reads below MAPQ, unmapped
and secondary records, a duplicate pair and a blacklist-overlapping pair.

| Boundary | Expected/observed alignments |
|---|---:|
| Input | 12 |
| After MAPQ/flags | 8 |
| Duplicates detected | 2 |
| After duplicate removal | 6 |
| After fragment blacklist | 4 |
| No-blacklist + duplicate-none branch | 8 |

Both final BAMs passed `samtools quickcheck`, received matching indexes and all
eight BAM-processing tasks were cached on resume. Separate expected-failure
runs rejected a reference length mismatch and a `1` versus `chr1` blacklist.

## Limitations

- The real reduced fixture validates paired-end only; single-end has a stub and
  an implemented provider path but no real regression in this stage.
- No production dataset benchmark or biological peak/FRiP validation was run.
- The OCI/Apptainer image declarations are pinned, but only the host SAMtools
  execution was tested here.
- Technical records are still processed independently; biological-library
  merging remains a future explicit stage.
- Peak calling, replicate concordance, consensus and differential binding are
  outside this API.
