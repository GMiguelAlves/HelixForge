# Licensing and third-party software

HelixForge source code, documentation, schemas, and synthetic test fixtures are
licensed under the [Apache License 2.0](../../LICENSE), except for explicitly
identified third-party files retaining their upstream license. The repository also ships a
[`NOTICE`](../../NOTICE) file with project attribution.

## Included source and fixtures

Selected nf-core/chipseq 2.1.0 files are included under
`vendor/nfcore_chipseq/2.1.0/`, with their original MIT license, copyright,
upstream commit and SHA-256 pins. The imported helper is unchanged; HF adapters
are separate. Attribution in publications complements, but does not replace,
preserving license notices. This reuse does not imply nf-core certification.
Versioned FASTQ, FASTA, GTF/GFF, BED and tabular test fixtures are synthetic;
biological study datasets are not redistributed here.

HelixForge invokes independent scientific tools such as Nextflow, FastQC,
MultiQC, Trim Galore, Bowtie2, samtools, STAR, Salmon, MACS3, deepTools, R,
Bioconductor, and DESeq2. Those tools are not relicensed by HelixForge; each
remains governed by its own upstream license. HOMER is also an external tool;
the selected 4.11 package records GPLv3 licensing. No HOMER binary/source is
included in this repository. Module metadata and environment
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
Before redistributing a derived HOMER image, inspect the exact package's license
and corresponding-source obligations; a tool citation alone is insufficient.
