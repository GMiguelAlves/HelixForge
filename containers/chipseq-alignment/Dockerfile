FROM mambaorg/micromamba:2.8.1-debian13-slim

COPY --chown=$MAMBA_USER:$MAMBA_USER \
    modules/local/bowtie2_align/environment.yml /tmp/environment.yml
RUN micromamba install --yes --name base --file /tmp/environment.yml \
    && micromamba clean --all --yes

ARG MAMBA_DOCKERFILE_ACTIVATE=1
RUN bowtie2 --version | sed -n '1p' | grep -F '2.5.4' \
    && samtools --version | sed -n '1p' | grep -F 'samtools 1.20'

# Nextflow bind mounts are owned by the invoking host user. Docker does not
# map that UID automatically, so the isolated runtime writes as container root.
USER root
