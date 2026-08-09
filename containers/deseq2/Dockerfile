FROM mambaorg/micromamba:1.5.8 AS micromamba

FROM quay.io/biocontainers/bioconductor-deseq2@sha256:2d299c5f045c65879e8da189bba17857963d50703af5410003e7e84883deef13

USER root
COPY --from=micromamba /bin/micromamba /usr/local/bin/micromamba
RUN MAMBA_ROOT_PREFIX=/usr/local micromamba install --yes --prefix /usr/local \
        --channel conda-forge --channel bioconda \
        bioconductor-rtracklayer=1.62.0 \
        r-pheatmap=1.0.12 \
        r-ggrepel=0.9.5 \
        r-jsonlite=1.8.8 \
    && MAMBA_ROOT_PREFIX=/usr/local micromamba clean --all --yes
RUN Rscript -e 'stopifnot(as.character(packageVersion("DESeq2")) == "1.42.0", as.character(packageVersion("rtracklayer")) == "1.62.0", as.character(packageVersion("pheatmap")) == "1.0.12", as.character(packageVersion("ggrepel")) == "0.9.5", as.character(packageVersion("jsonlite")) == "1.8.8")'
