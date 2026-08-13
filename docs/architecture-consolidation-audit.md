# Native architecture consolidation audit

## Scope and evidence level

The audit covered the actual DSL2 workflows, subworkflows, native modules,
configuration, schemas, channel composition and manifest producers for RNA-seq,
ChIP-seq, Integrative and `all`. No file under `pipelines/*/legacy/` was changed.
Only static and lightweight execution checks belong to this consolidation; no
scientific equivalence is claimed.

## Corrected problems

1. Forced RNA modes did not gate both providers. `alignment` could still launch
   Salmon and `quantification` could still launch STAR when their native flags
   were true. Provider execution is now derived from the effective analysis
   mode.
2. An RNA pipeline configured for STAR could stop before Import/DE merely
   because `analysis_mode=alignment`. Only explicit stage-stop modes now stop;
   `full` and DE modes may consume STAR through the Import API.
3. ChIP records were combined with every Bowtie2 index. Multiple references
   could create an all-by-all product. Both channels now carry the same explicit
   `genome_id|directory|basename` key and combine by that key.
4. BAM-processing manifests were isolated files. Alignment, selection,
   duplicate, blacklist and final-BAM manifests now form a checksum lineage.
5. Aggregate Peak QC, Consensus, Annotation and Track manifests lacked a stable
   top-level identity. Deterministic aggregate IDs were added, including stubs.
6. Boundary Alignment, Quantification and Import manifests did not consistently
   report state. Native success and stub manifests now state their status.
7. The common manifest schema described a retired array model unrelated to
   native outputs. It now defines the extensible v1 envelope actually exchanged
   by APIs.
8. `nextflow_schema.json` omitted 89 accepted parameters and omitted native
   ChIP modes `annotation`, `tracks`, and `report`. It now inventories all 160
   parameters declared by `nextflow.config`.
9. Product, environment, schema-domain, documentation and container names were
   mixed between brands. They are now HelixForge throughout native code.

## Deliberate compatibility boundaries

- Historical status at the time of this audit: ChIP `full` remained the legacy
  graph. This item was superseded by the native coordinator documented in
  [chipseq-full-native-validation.md](chipseq-full-native-validation.md); the
  legacy sources themselves remain available as the rollback boundary.
- Integrative remains legacy and currently consumes paths from its configuration;
  `all` provides a completion barrier, not semantic RNA/ChIP artifacts.
- RNA download, metadata/reference preparation and remaining final reporting
  wrappers are unchanged.
- `rnaseq_native_import=false` is rejected where Import is required; there is no
  longer a supported tximport wrapper to fall back to.
- Historical finding: IDR had no scientific provider at audit time. This was
  superseded by the optional pinned IDR 2.0.4.2 provider; historical unavailable
  manifests remain supported by the fail-honest report contract.
- The historical uppercase environment-variable prefix appears only at the
  legacy adapter boundary because immutable legacy scripts read those exact names. This is a
  compatibility token, not product branding.

## Parameter and mode decisions

- `rnaseq_run_mode=alignment` means STAR only; `quantification` means Salmon
  only; `both` remains independent fan-out.
- In `config`, native flags permit both provider plans to exist, while the
  authoritative plan and Import provider select the consumed result.
- Native ChIP standalone annotation, tracks and report modes require explicit
  manifests/inventories. No directory glob is used for semantic discovery.
- Scientific defaults and legacy-compatible output locations were not changed.
- Container repository names changed to `helixforge-*`; they must be published
  before container-profile scientific validation.

## Remaining scientific risks

- No legacy-versus-native real-data comparison was executed in this audit.
- Renamed OCI images may not exist until the updated CI publishes them.
- Integrative identifier/reference compatibility is not yet enforced by a
  common manifest inventory.
- ChIP `full`, production Slurm behavior, container digests and cache
  invalidation still require the mandatory validation battery.
- Exact numerical/serialization equivalence for tximport, DESeq2, MACS3,
  featureCounts, annotations and BigWig tracks remains unproven here.

The execution and acceptance matrix is maintained in
[final validation plan](final-validation-plan.md).

## Lightweight validation result

- Architecture contract checks: **PASS** (5 checks).
- Python compilation for changed manifest/report helpers: **PASS**.
- JSON parsing for root, schema and asset specifications: **PASS**.
- Git whitespace/error check: **PASS**.
- Nextflow lint and stub execution: **NOT RUN** because `nextflow` is not
  installed in the available WSL environment. No runtime or dependencies were
  downloaded. This is an environment limitation, not a successful validation.
