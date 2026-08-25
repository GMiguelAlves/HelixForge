# RNA-seq benchmark dataset registry

This registry is normative for Stage 9B. Dataset substitutions require a new
protocol version and must not silently replace the entries below.

## Level A — simulated truth

| Field | Frozen value |
|---|---|
| Dataset ID | `polyester_human_v1` |
| Simulator | Polyester 1.38.0, Bioconductor 3.18 / R 4.3 |
| Reference | GENCODE v49, GRCh38.p14 primary assembly |
| Layout | paired-end, 75 bp |
| Samples | 6: 3 control and 3 treatment |
| Truth | transcript counts, gene counts, TPM and gene log2 fold changes |
| Design | `~ condition` |
| Purpose | quantification accuracy, DE truth recovery and reproducibility |

The complete frozen design is in `../configs/synthetic_design.json`. Polyester
emits paired FASTA reads. Stage 9B converts them deterministically to FASTQ with
constant Phred 40 qualities; simulated sequence errors remain unchanged. This
level therefore validates quantification and differential expression, not the
realism of adapter/quality trimming.

## Level B — public biological data

| Field | Frozen value |
|---|---|
| Dataset ID | `gse52778_airway` |
| GEO | GSE52778 |
| SRA/ENA study | SRP033351 / PRJNA229998 |
| Assay | human airway smooth-muscle cells, 75 bp paired-end RNA-seq |
| Samples | untreated and dexamethasone for each of four donors (8 libraries) |
| Design | `~ batch + condition`, where `batch` is donor |
| Contrast | `condition_dexamethasone_vs_untreated` |
| Purpose | top-level behavior, robustness to depth and biological plausibility |

The exact eight ENA runs, URLs and source MD5 digests are frozen in
`airway_samples.tsv`. Only `_1.fastq.gz` and `_2.fastq.gz` are inputs. Any
additional unpaired file listed by ENA for a run is excluded.

The publication used hg19, fixed read cropping and Cufflinks/Cuffdiff. Therefore
its reported 316 genes at BH-adjusted p-value < 0.05 and highlighted genes are
used only as `SET_OVERLAP` or `BIOLOGICAL_EXPECTATION` evidence. They are not an
exact or numeric reference for the HelixForge GRCh38/Salmon/DESeq2 analysis.

Expected positive controls include `DUSP1`, `KLF15`, `PER1`, `TSC22D3` and
`CRISPLD2`. `B2M`, `GABARAP`, `GAPDH` and `RPL19` are publication-reported highly
expressed non-differential checks. These are sanity checks, not release gates.

## Reference bundle

All benchmark levels use the sources in `reference_sources.tsv`. Stage 9B must:

1. download each source exactly once on a Slurm execution node;
2. record upstream and computed SHA-256 checksums;
3. derive the primary-assembly transcriptome from GTF transcript IDs;
4. retain transcript versions and rewrite each FASTA identifier to the first
   pipe-delimited token, matching the frozen Import policy;
5. record the derivation command and checksums in provenance.

No reference or FASTQ payload is committed to Git.

## Sources

- Frazee et al. 2015, Polyester: <https://doi.org/10.1093/bioinformatics/btv272>
- Himes et al. 2014, airway response: <https://doi.org/10.1371/journal.pone.0099625>
- GEO GSE52778: <https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE52778>
- GENCODE Human Release 49: <https://www.gencodegenes.org/human/release_49.html>
