FROM mambaorg/micromamba:2.8.1-debian13-slim

COPY --chown=$MAMBA_USER:$MAMBA_USER \
    modules/local/frip/environment.yml /tmp/environment.yml
RUN micromamba install --yes --name base --file /tmp/environment.yml \
    && micromamba clean --all --yes

ARG MAMBA_DOCKERFILE_ACTIVATE=1
RUN python --version 2>&1 | grep -F '3.12.4' \
    && samtools --version | sed -n '1p' | grep -F 'samtools 1.20' \
    && bedtools --version | grep -F 'v2.31.1'

USER root
