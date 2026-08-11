FROM mambaorg/micromamba:1.5.8

COPY --chown=$MAMBA_USER:$MAMBA_USER \
    modules/local/deseq2_model/environment.yml /tmp/environment.yml
RUN micromamba install --yes --name base --file /tmp/environment.yml \
    && micromamba clean --all --yes

ARG MAMBA_DOCKERFILE_ACTIVATE=1
RUN Rscript -e 'stopifnot(as.character(getRversion()) == "4.3.3", as.character(packageVersion("DESeq2")) == "1.42.0", as.character(packageVersion("rtracklayer")) == "1.62.0", as.character(packageVersion("ggplot2")) == "3.5.1", as.character(packageVersion("pheatmap")) == "1.0.12", as.character(packageVersion("matrixStats")) == "1.3.0", as.character(packageVersion("ggrepel")) == "0.9.5", as.character(packageVersion("jsonlite")) == "1.8.8")'
