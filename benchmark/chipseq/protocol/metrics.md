# Frozen metric definitions

All interval calculations use zero-based, half-open coordinates after sorting
and exact-union reduction. Undefined ratios are emitted as `NA` with a reason,
never coerced to zero. Formulas are computed per replicate and for the declared
final replicate set.

## Narrow metrics

| Metric | Definition and inputs | Unit / interpretation | Edge cases |
|---|---|---|---|
| Precision | `matched_calls / all_called_peaks`; matching is frozen in the protocol. | fraction; call-level discrimination | No calls → `NA`, not 1. |
| Recall | `matched_truth_peaks / 1500`. | fraction; truth recovery | No calls → 0. |
| F1 | `2PR/(P+R)`. | fraction | `NA` if precision undefined. |
| Observed FDP | `unmatched_calls / all_called_peaks`. | fraction; equals `1-precision` when defined | Not interpreted as MACS q-value calibration. |
| Candidate AUPRC | Average precision over 1,500 fixed positive and 1,500 matched-negative 1 kb windows, scored by maximum overlapping MACS signal or zero. | area 0–1; prevalence baseline 0.5 | Report ties and zero-score fraction. |
| Summit distance | Absolute called-summit minus true-summit coordinate for matched pairs. | bp; median, IQR, 90th percentile | Broad outputs excluded; missing summit → `NA`. |
| Width error | `log2(called_width / 400)` for matched pairs; also absolute bp error. | log2 ratio / bp | Zero/invalid widths fail validation. |
| Rank concordance | Spearman correlation of frozen truth strength and MACS signal among matched peaks. | rho | Fewer than 10 pairs → `NA`. |
| Recall by strength | Recall independently for 500 STRONG, MEDIUM and WEAK peaks. | fraction | Class labels come only from simulation input. |
| Replicate overlap | Base Jaccard and reciprocal overlap of per-replicate peak unions. | fraction | Report both directions for unequal sets. |
| Replicate rank concordance | Spearman correlation of MACS signal on one-to-one replicate peak matches. | rho | Same deterministic matching/tie policy. |
| Narrow fragmentation | Fraction of truths with >1 eligible called neighbour; extra calls count as FP. | fraction | Does not alter primary matching. |
| FRiP | HelixForge numerator/denominator from final BAM and per-replicate peaks, using frozen unit and any-base overlap. | fraction | Input FRiP is descriptive only. |

Primary narrow accuracy is precision, recall, F1, observed FDP and summit
distance. AUPRC is candidate-panel evidence and cannot replace genome-wide
precision.

## Broad metrics

Let `T` be the union of true-domain bases and `C` the union of called-domain
bases.

| Metric | Definition and inputs | Unit / interpretation | Edge cases |
|---|---|---|---|
| Base precision | `|T∩C| / |C|`. | fraction | Empty `C` → `NA`. |
| Base recall | `|T∩C| / |T|`. | fraction | Empty truth is an invalid fixture. |
| Base F1 | harmonic mean of base precision/recall. | fraction | `NA` when precision undefined. |
| Intersection / union | Exact union-reduced lengths `|T∩C|` and `|T∪C|`. | bp | Recorded to make ratios auditable. |
| Global IoU | `|T∩C| / |T∪C|`. | fraction | Empty union invalid. |
| Per-domain IoU | Truth interval versus union of substantially connected calls. | fraction; median/IQR and distribution | No substantial call → 0. |
| Boundary error | Absolute left and right boundary differences for one-truth/one-call components. | bp; signed and absolute summaries | Complex components excluded and counted topologically. |
| Coverage recall | Fraction of each truth domain covered by union of all calls. | fraction | Used for the 50% recovered rule. |
| Fragmentation rate | Truth domains with ≥2 substantial call neighbours / 360; excess is sum `degree-1`. | fraction and count | An overlap <500 bp or <10% truth does not create substantial edge. |
| Merging rate | Calls with ≥2 substantial truth neighbours / number of calls; excess is sum `degree-1`. | fraction and count | Empty calls → `NA` rate and zero recovery. |
| Coverage correlation | Pearson and Spearman correlation between frozen expected-signal vector and CPM BigWig in non-overlapping 500 bp eligible-genome bins. | r/rho | Constant vectors → `NA`; blacklist/repeats excluded identically. |
| Recall by width/strength | Domain recovered at ≥50% coverage, stratified by the nine frozen width × strength cells. | fraction | Every cell has exactly 40 domains. |
| Replicate coverage correlation | Pearson/Spearman of replicate CPM coverage in the same 500 bp bins. | r/rho | No post-hoc high-signal bin selection. |
| Replicate consensus | Base precision/recall of replicate-support set relative to truth plus overlap with each replicate. | fraction | Primary broad final set requires support=2. |
| FRiP | Same frozen HelixForge definition using broadPeak intervals. | fraction | Not compared directly with narrow FRiP as an assay-quality ranking. |

Summit distance is not calculated for broad domains.

## Real-data metrics

- FastQC/MultiQC observations; read count and retention; Bowtie2 overall
  alignment; MAPQ distribution and fraction retained; duplicate-flag fraction;
  blacklist removal; final BAM size/checksum; FRiP; peak/domain count and width;
  genomic annotation distribution; and descriptive overlap with the selected
  ENCODE processed reference.
- Narrow adds replicate peak Jaccard, rank correlation, IDR count/fraction and
  CTCF motif enrichment in ±100 bp around summits against chromosome/GC-matched
  controls.
- Broad adds 500 bp-bin replicate coverage correlation, base overlap,
  replicated-domain overlap, width distribution and coverage at predeclared
  locus sets.
- Peak-to-gene results are a separate interpretation table. They are never
  included in peak-calling precision or called a causal target map.
- NRF/PBC and cross-correlation are marked unavailable because HelixForge does
  not currently implement them. Duplicate statistics are not mislabeled as
  complete library-complexity assessment.

## Reproducibility metrics

The evaluator records identical semantic artifact sets, coordinate equality or
declared tolerance, checksum stability for deterministic text, peak-set
Jaccard, rank correlations and differences between first and repeated runs.
IDR evaluates replicate reproducibility only. It is never reported as truth
accuracy.

## Performance metrics

From Nextflow trace, report and Slurm accounting collect wall time, CPU time,
peak RSS, read/write volume, task count, maximum concurrent jobs, work size and
result size. Values are labelled `DESCRIPTIVE_CLUSTER_PERFORMANCE`; the shared
university cluster is not a speed competition and queued time is separated from
execution time.
