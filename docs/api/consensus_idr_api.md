# Consensus / IDR API v1

Consensus/IDR API v1 consolidates evidence across explicitly identified
ChIP-seq replicates. Consensus and IDR are distinct strategies with different
scientific meanings and providers. A union is reported as `strategy=union`; it
is never presented as generic reproducibility or IDR evidence.

## Input contract

Each experiment group contains:

- Peak Calling manifests and semantic peak result directories;
- per-replicate Peak QC manifests;
- dataset, experiment, condition/treatment, target, control association, and genome/build;
- biological and technical replicate identifiers;
- explicit narrowPeak or broadPeak type and caller provenance;
- replicate mode and policy;
- one strategy and its explicit parameters.

The grouping key is dataset + experiment + condition + target + genome + peak
type. Channel order, globs, partial filenames, and list position are never
biological identity. Caller compatibility is validated inside a group so
incompatible callers cannot be silently split into apparently valid groups.

## Replicate contract

`replicate_mode=biological` requires `replicate_policy=require_premerged` in
v1. Each biological replicate must therefore have exactly one upstream peak
set. Multiple uncollapsed technical records fail with an instruction to define
a future technical-replicate aggregation provider.

`replicate_mode=technical` requires `replicate_policy=preserve`. Each unique
biological/technical pair remains an independent evidence unit. The API never
merges technical replicates silently.

At least two evidence units are required. Missing IDs, duplicate replicate
keys, cross-experiment inputs, mixed peak types/builds/datasets/treatments, and
caller mismatches under `require_same_caller=true` fail during context
validation.

## Consensus providers

All implemented consensus methods use half-open genomic intervals and preserve
the original peak files as replicate evidence. Within each replicate,
overlapping intervals are merged before cross-replicate comparison. BEDTools
`multiinter` then produces atomic, non-overlapping segments with a constant
support set.

- `union`: retain atomic segments supported by at least one replicate;
- `intersection`: retain segments supported by every replicate;
- `replicate_support`: retain segments supported by at least the explicit
  `min_replicates` value, which must be between 2 and the number of evidence
  units.

An additional opt-in broad provider, `regional_catalog` (`regional_catalog_v1`
1.0.0), preserves complete candidate envelopes and publishes the atomic support
core separately. Its `consolidated_bed` is the candidate catalog, **not confirmed
occupancy**. The long-form support matrix includes called bases/fractions for
every library, including zero support. Classification distinguishes `candidate`
from `spatially_supported_candidate`; both have `occupancy_status=not_assessed`.
See the [provider contract](../../modules/local/regional_catalog/README.md).
The [prospective synthetic validation](../../validation/broad_consensus/regional_catalog_v1/RESULTS.md)
passed 18 new aligned-read cases and native runtime/cache tests. This is not
biological-occupancy certification; existing strategies/defaults and pinned
results are not replaced by this opt-in implementation.

For the three atomic strategies, adjacent segments with different support sets are not merged. This avoids
fabricating one support value for a region whose evidence changes across its
length. Output columns are `peak_id`, `chrom`, `start`, `end`, `support`, and
`support_replicates`.

Scores, summits, signalValue, p-values, and q-values are not combined in v1:
there is no universal defensible aggregation rule. Exact per-replicate peak
records are retained in an evidence table and referenced by the manifest.
BroadPeak remains broadPeak evidence and is never converted to narrowPeak.

For broad inputs, the consolidated intervals are **per-base support cores**,
not inferred complete broad domains. Subintervals shorter than the caller's
minimum peak length, including one-base overlaps, can arise legitimately from
the intersection operation. A high fraction of discarded input-union coverage
requires scientific review; it must not be described automatically as improved
specificity. See the [broad-peak representation guide](../guides/broad-peak-consensus.md)
and its controlled comparison tool before using this layer as an exhaustive
gene-association or occupancy catalog.

## IDR provider

IDR is a statistical reproducibility strategy, not interval intersection. The
v1 provider validates exactly two premerged biological replicates, narrowPeak
input, an explicit `idr_threshold`, and an explicit rank metric. It executes
IDR `2.0.4.2`, maps `signal_value`, `p_value`, or `q_value` to the corresponding
narrowPeak rank, fixes `--random-seed 0`, and records the complete command.

The provider emits the filtered raw IDR narrowPeak result, plot when produced,
local/global IDR values, provider-neutral BED/table roles, evidence checksums,
statistics, versions and execution metadata. `complete_empty` is a valid
statistical result and never falls back to interval consensus. Upstream peak
lists should be sufficiently permissive; HelixForge does not silently relax the
MACS3 cutoff.

## Output contract

Implemented Consensus and IDR providers emit:

- a consolidated interval table and BED file;
- exact replicate support per segment;
- preserved per-replicate evidence;
- peak/support statistics;
- strategy and parameters;
- versions, execution metadata, structured provenance, manifest, and status.

The aggregate manifest preserves experiment, condition, treatment, control
associations, replicate identities, input peak IDs, genome/build, peak type,
caller provenance, and consolidated artifact roles for a future Differential
Binding API.

## Cache semantics

Peak directories/manifests, Peak QC manifests, metadata, grouping identity,
replicate mode/policy, strategy, support threshold, IDR threshold/rank metric,
peak type, caller policy, genome, and provider version are tracked process
inputs under deep cache. Changing one group invalidates only its context,
provider, and the lightweight global aggregate.
