FROM mambaorg/micromamba:2.8.1-debian13-slim

COPY --chown=$MAMBA_USER:$MAMBA_USER \
    containers/chipseq-tracks/environment.yml /tmp/environment.yml
RUN micromamba install --yes --name base --file /tmp/environment.yml \
    && micromamba clean --all --yes

ARG MAMBA_DOCKERFILE_ACTIVATE=1
RUN python --version 2>&1 | grep -F '3.11.9' \
    && bamCoverage --version | grep -F '3.5.5' \
    && samtools --version | sed -n '1p' | grep -F 'samtools 1.20' \
    && python -c 'import pyBigWig; assert pyBigWig.__version__ == "0.3.23"'

USER root
