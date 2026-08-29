# Frozen ChIP-seq dataset registry

## Selection rationale

The real-data arms use K562 experiments produced by the same ENCODE laboratory
and the same Input experiment. This controls cell line, organism, assembly,
laboratory and control source while retaining the distinct biology required for
narrow and broad peaks.

| Field | Real narrow | Real broad |
|---|---|---|
| Accession | `ENCSR000AKO` | `ENCSR000AKQ` |
| Assay / target | ChIP-seq / CTCF | ChIP-seq / H3K27me3 |
| Organism | *Homo sapiens* | *Homo sapiens* |
| Cell line | K562 | K562 |
| Biological replicates | 2 | 2 (replicates 1 and 2 selected) |
| Control | `ENCSR000AKY`, Input library | `ENCSR000AKY`, Input library |
| Layout | Single-end | Single-end |
| Assembly | GRCh38 | GRCh38 |
| Source | ENCODE Project portal | ENCODE Project portal |
| Publication context | ENCODE Project Consortium, 2012, DOI `10.1038/nature11247` | ENCODE Project Consortium, 2012, DOI `10.1038/nature11247` |
| Approximate compressed download | 2.22 GiB | 2.46 GiB |
| Selection reason | Localized, motif-bearing TF signal with two biological replicates and matched Input | Canonical broad Polycomb-associated mark with two biological replicates and matched Input |
| Main limitation | Legacy experiment; 36/51 bp reads and ENCODE compliance warnings | Legacy experiment; 51/36 bp reads and heterogeneous platform history |

Because the Input FASTQ is shared, the unique total for both real arms is about
4.19 GiB. Exact files, byte sizes, read counts, checksums and URLs are frozen in
[`real_narrow_samples.tsv`](real_narrow_samples.tsv) and
[`real_broad_samples.tsv`](real_broad_samples.tsv).

## Narrow: K562 CTCF

`ENCSR000AKO` supplies two biological replicates. CTCF is appropriate for a
narrow benchmark because it produces localized enrichment and has a canonical
sequence motif. The experiment is a legacy ENCODE record with differing read
lengths (36 bp and 51 bp) and ENCODE compliance warnings. Those properties are
part of the frozen dataset and must be reported; reads must not be trimmed to
make the replicates artificially homogeneous.

External ENCODE optimal IDR peaks `ENCFF519CXF` and signal track
`ENCFF433VSV` are used only for plausibility comparisons. They are not truth,
training data or HelixForge inputs.

## Broad: K562 H3K27me3

`ENCSR000AKQ` supplies biological replicates 1 and 2. H3K27me3 is a canonical
broad Polycomb-associated repressive mark and tests continuous-domain recovery
rather than summit localization. These replicates also differ in read length
(51 bp and 36 bp), which is retained and documented.

External ENCODE replicated peaks `ENCFF049HUP` and signal track `ENCFF366NNJ`
are descriptive references only. The benchmark must not tune thresholds to
maximize agreement with ENCODE processing.

## Control semantics

`ENCSR000AKY` is declared by ENCODE as an Input library. It is shared by the
two experiments and is not an IgG control. HelixForge metadata must retain the
role `INPUT`; no conversion between Input and IgG semantics is allowed.

## Reference

Both real arms use the same frozen bundle:

- GENCODE release 50 GRCh38 primary-assembly FASTA and primary-assembly GTF;
- effective genome size `2913022398`;
- ENCODE GRCh38 blacklist `ENCSR636HFF` / `ENCFF356LFX`;
- source MD5 plus decompressed SHA-256 recorded before execution;
- unmodified contig identifiers, with a hard failure on mismatches.

The authoritative source inventory is
[`reference_sources.tsv`](reference_sources.tsv). Downloads must be verified
against that inventory and copied into the benchmark manifest before use.

## Exclusions

- No downsampling is part of this baseline.
- No pseudoreplicates are substituted for biological replicates.
- No processed ENCODE peak file is treated as experimental truth.
- No broad IDR gate is introduced.
- No biological dataset is downloaded or executed by this design branch.

## Primary sources

- [ENCODE K562 CTCF experiment](https://www.encodeproject.org/experiments/ENCSR000AKO/)
- [ENCODE K562 H3K27me3 experiment](https://www.encodeproject.org/experiments/ENCSR000AKQ/)
- [ENCODE Input experiment](https://www.encodeproject.org/experiments/ENCSR000AKY/)
- [ENCODE GRCh38 blacklist](https://www.encodeproject.org/annotations/ENCSR636HFF/)
- [GENCODE human release 50](https://www.gencodegenes.org/human/)
- [ENCODE Project Consortium publication](https://doi.org/10.1038/nature11247)
