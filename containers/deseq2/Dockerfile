FROM quay.io/biocontainers/bioconductor-deseq2@sha256:2d299c5f045c65879e8da189bba17857963d50703af5410003e7e84883deef13

USER root
RUN apt-get update \
    && apt-get install --yes --no-install-recommends libxml2-dev \
    && rm -rf /var/lib/apt/lists/*
RUN Rscript -e 'install.packages(c("BiocManager", "remotes"), repos="https://cloud.r-project.org")' \
    && Rscript -e 'remotes::install_version("pheatmap", version="1.0.12", repos="https://cloud.r-project.org", upgrade="never")' \
    && Rscript -e 'remotes::install_version("ggrepel", version="0.9.5", repos="https://cloud.r-project.org", upgrade="never")' \
    && Rscript -e 'remotes::install_version("jsonlite", version="1.8.8", repos="https://cloud.r-project.org", upgrade="never")'
RUN Rscript -e 'BiocManager::install("rtracklayer", version="3.18", ask=FALSE, update=FALSE)'
RUN Rscript -e 'stopifnot(as.character(packageVersion("DESeq2")) == "1.42.0", as.character(packageVersion("rtracklayer")) == "1.62.0", as.character(packageVersion("pheatmap")) == "1.0.12", as.character(packageVersion("ggrepel")) == "0.9.5", as.character(packageVersion("jsonlite")) == "1.8.8")'
