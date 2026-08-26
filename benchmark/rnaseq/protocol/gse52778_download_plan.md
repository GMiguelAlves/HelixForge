# GSE52778 full-data download plan

- Runs: 8
- NCBI SRA/SRA-Lite alternative: 16.36 GiB
- Selected official ENA paired FASTQ transfer: 20.23 GiB
- Paired spots retained: 195,411,576
- FASTQ uncompressed sequence+quality lower bound: 45.86 GiB
- Conservative uncompressed FASTQ planning estimate: 57.33 GiB
- Temporary uncompressed FASTQ for chosen strategy: 0 GiB
- Reference and Salmon index reserve: 60 GiB
- Nextflow work reserve: 250 GiB
- Results reserve: 20 GiB
- Safety margin: 25%
- Required scratch planning envelope: 437.79 GiB

The selected strategy downloads the exact paired ENA exports already frozen in
`airway_samples.tsv`. Additional orphan/unpaired exports are excluded. Transfer
uses resumable partial files, official MD5 validation, local SHA-256 and paired
FASTQ structural validation. SRA conversion is not used, avoiding the
simultaneous SRA and uncompressed FASTQ footprint.

## Metadata warning

GEO describes 75 bp sequencing, while the deposited ENA/SRA descriptors contain
two 63 bp application reads (126 bp per paired spot). The frozen accessions,
GSMs, donors, conditions, layout, platform, file sizes and MD5 values all match.
The benchmark evaluates the deposited paired FASTQs and records this distinction.
