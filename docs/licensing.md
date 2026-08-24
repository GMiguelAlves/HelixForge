# Licensing and third-party software

HelixForge source code, documentation, schemas, and synthetic test fixtures are
licensed under the [Apache License 2.0](../LICENSE). The repository also ships a
[`NOTICE`](../NOTICE) file with project attribution.

## Audit scope

The release-candidate audit found no vendored third-party source tree, Git
submodule, externally sourced binary asset, or redistributed biological dataset
in the source repository. Versioned FASTQ, FASTA, GTF/GFF, BED, and tabular test
fixtures are synthetic project fixtures.

HelixForge invokes independent scientific tools such as Nextflow, FastQC,
MultiQC, Trim Galore, Bowtie2, samtools, STAR, Salmon, MACS3, deepTools, R,
Bioconductor, and DESeq2. Those tools are not relicensed by HelixForge; each
remains governed by its own upstream license. Module metadata and environment
files identify the applicable providers and versions.

## Container images

Project-built container images are aggregate distributions: the HelixForge
wrappers in them are Apache-2.0, while installed operating-system, Conda,
Bioconda, CRAN, and Bioconductor packages retain their respective licenses.
Publishing an image must preserve the license metadata and notices supplied by
those packages. A container's contents must be audited independently whenever
its base image or dependency lock changes.

The Apache-2.0 license for HelixForge does not replace, weaken, or satisfy a
third-party component's separate redistribution obligations.
