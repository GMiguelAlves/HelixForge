FROM mambaorg/micromamba:1.5.8

COPY --chown=$MAMBA_USER:$MAMBA_USER \
    modules/local/rnaseq_gene_report/environment.yml /tmp/environment.yml
RUN micromamba install --yes --name base --file /tmp/environment.yml \
    && micromamba clean --all --yes

ARG MAMBA_DOCKERFILE_ACTIVATE=1
RUN Rscript -e 'stopifnot(as.character(getRversion()) == "4.3.3", as.character(packageVersion("readr")) == "2.1.5", as.character(packageVersion("dplyr")) == "1.1.4", as.character(packageVersion("tidyr")) == "1.3.1", as.character(packageVersion("stringr")) == "1.5.1", as.character(packageVersion("ggplot2")) == "3.5.1", as.character(packageVersion("pheatmap")) == "1.0.12", as.character(packageVersion("rtracklayer")) == "1.62.0")'

# Nextflow bind-mounts work directories owned by the invoking host UID. Docker
# does not map that UID automatically; using root inside the isolated container
# keeps the image portable across runners without privileged host execution.
USER root
