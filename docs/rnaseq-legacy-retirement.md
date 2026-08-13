# RNA-seq legacy retirement

The RNA-seq shell pipeline was removed from the active source tree after the
native production path passed final synthetic validation locally, in CI, and on
Slurm. The immutable tag `rnaseq-legacy-v1.0.0` points to the last reviewed
revision that contains the complete legacy implementation.

The supported path is:

```text
FASTQ -> QC -> Salmon -> Import/tximport -> DESeq2 -> Gene Report
```

STAR remains an optional experimental Alignment API provider. Data download is
outside the scientific workflow. Matrix batch correction is not an inferential
input; batch belongs in an estimable DESeq2 design such as
`~ batch + condition`. Exploratory Batch Effect Assessment remains on the
roadmap.

The current tree retains only the transitional shell configuration contract in
`pipelines/rnaseq/config` and module-owned planning adapters. Neither contains a
scientific executor or submits Slurm jobs.

Manual legacy-versus-native regression scripts use
`tests/lib/materialize_rnaseq_legacy.sh` to read the exact reference source from
the tag. A shallow clone must fetch the tag before running those optional
historical comparisons:

```bash
git fetch origin tag rnaseq-legacy-v1.0.0
```

Normal unit, contract, stub, and production workflows do not require the tag.
