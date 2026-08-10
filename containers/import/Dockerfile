FROM mambaorg/micromamba:2.8.1-ubuntu22.04@sha256:e6109b71ce41db7d3ef6084751a6be005420308847737cc8d758d14c4ecf86ed

LABEL org.opencontainers.image.source="https://github.com/GMiguelAlves/HelixForge"
LABEL org.opencontainers.image.description="Pinned R/Bioconductor runtime for HelixForge Import API"
LABEL org.opencontainers.image.version="1.0.0"

COPY --chown=$MAMBA_USER:$MAMBA_USER modules/local/tximport/environment.yml /tmp/environment.yml
RUN micromamba install --yes --name base --file /tmp/environment.yml \
    && micromamba clean --all --yes

USER root
RUN apt-get update \
    && apt-get install --yes --no-install-recommends procps \
    && rm -rf /var/lib/apt/lists/*
USER $MAMBA_USER

ARG MAMBA_DOCKERFILE_ACTIVATE=1
